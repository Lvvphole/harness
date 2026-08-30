from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .envelope import as_edits, content_sha256, hash_proposal, is_candidate
from .evidence import make_record
from .gates import authorize_tool, decide, evaluate_inference
from .hooks import HookRegistry
from .state import Phase, RunState
from .worktree import PatchError, WorktreeTransaction

ToolExecutor = Callable[[dict[str, Any], dict[str, Any]], tuple[bool, str]]
OracleRunner = Callable[[dict[str, Any], Path], bool]
MUTATING_TOOLS = {"write_file"}


class Controller:
    def __init__(
        self,
        authoritative: Path,
        contract: dict[str, Any],
        evidence_dir: Path,
        run_id: str = "run-001",
        known_secrets: set[str] | None = None,
        oracle_runner: OracleRunner | None = None,
        tool_executor: ToolExecutor | None = None,
    ):
        self.authoritative = Path(authoritative)
        self.contract = contract
        self.evidence_dir = Path(evidence_dir)
        self.known_secrets = known_secrets
        self.oracle_runner = oracle_runner
        self.tool_executor = tool_executor
        self.state = RunState(run_id, contract)
        self.hooks = HookRegistry()
        self.records: list[dict[str, Any]] = []

    def ingest_proposal(self, raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
        self.state.advance(Phase.REQUEST_PROPOSAL)
        self.state.attempt += 1
        self.state.turns += 1
        self.hooks.emit("before_next_turn", state=self.state.snapshot())

        if self.state.turns > self.contract["budget"]["max_turns"]:
            self.hooks.emit("on_budget_exhausted", state=self.state.snapshot())
            self.state.advance(Phase.BLOCKED)
            return self._halt_record("0000" * 16, "turn budget exhausted")

        self.state.advance(Phase.VALIDATE_GENERATION)
        gates, reasons, parsed = evaluate_inference(
            raw,
            self.contract,
            self.authoritative,
            self.state.attempt,
            self.known_secrets,
        )
        proposal_sha = hash_proposal(parsed) if parsed else "0" * 64
        self.state.proposal_sha256 = proposal_sha
        decision = decide(gates)

        if decision == "REJECT" and gates.get("retry_policy") == "FAIL":
            decision = "HALT"

        if decision != "ACCEPT" or parsed is None:
            return self._persist(proposal_sha, gates, decision, reasons, parsed)

        self.hooks.emit(
            "before_model_output_accepted",
            proposal=parsed,
            sha256=proposal_sha,
            state=self.state.snapshot(),
        )
        self.state.write_authorized = True

        staged_writes, pending_exec, auth_fail = self._authorize_tools(parsed)
        if auth_fail is not None:
            self.state.write_authorized = False
            self.state.advance(Phase.BLOCKED)
            return self._persist(proposal_sha, gates, "HALT", reasons + [auth_fail], parsed)

        edits = as_edits(parsed, self.authoritative) + staged_writes
        if staged_writes:
            preview = {
                "schema_version": "1.0",
                "contract_id": parsed["contract_id"],
                "intent": "edit",
                "edits": [
                    {
                        "path": e["path"],
                        "action": e["action"],
                        "unified_diff": e.get("unified_diff", ""),
                        **({"source": e["source"]} if "source" in e else {}),
                    }
                    for e in edits
                ],
                "tool_calls": [],
            }
            extra_gates, extra_reasons, _ = evaluate_inference(
                preview,
                self.contract,
                self.authoritative,
                self.state.attempt,
                self.known_secrets,
            )
            if decide(extra_gates) != "ACCEPT":
                self.state.write_authorized = False
                return self._persist(
                    proposal_sha,
                    extra_gates,
                    "HALT",
                    reasons + extra_reasons,
                    parsed,
                )

        try:
            with WorktreeTransaction(self.authoritative) as txn:
                txn.bind(proposal_sha, edits)
                txn.apply_to_temp(edits)
                for call in pending_exec:
                    ok, reason = self._execute_on_temp(call, txn.temp)
                    if not ok:
                        self.state.write_authorized = False
                        self.state.advance(Phase.BLOCKED)
                        return self._persist(
                            proposal_sha, gates, "HALT", reasons + [reason], parsed
                        )
                if self.oracle_runner:
                    self.state.advance(Phase.RUN_ORACLE)
                    ok = self.oracle_runner(self.contract, txn.temp or self.authoritative)
                    if not ok:
                        self.state.write_authorized = False
                        self.state.advance(Phase.FAIL)
                        return self._persist(
                            proposal_sha,
                            gates,
                            "HALT",
                            reasons + ["oracle failed"],
                            parsed,
                        )
                self.hooks.emit("before_state_commit", sha256=proposal_sha)
                txn.commit(proposal_sha)
        except (PatchError, OSError, RuntimeError) as exc:
            self.state.write_authorized = False
            self.state.advance(Phase.FAIL)
            return self._persist(
                proposal_sha, gates, "HALT", reasons + [str(exc)], parsed
            )
        self.state.files_touched += len({e["path"] for e in edits})
        self.hooks.emit("after_mutation", paths=[e["path"] for e in edits])
        self.state.advance(Phase.COMMIT)
        self.state.advance(Phase.PASS)
        return self._persist(proposal_sha, gates, "ACCEPT", reasons, parsed)

    def _authorize_tools(
        self, parsed: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
        staged: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        for call in parsed.get("tool_calls") or []:
            try:
                ok, reason = self.authorize_and_maybe_execute(call, execute=False)
            except Exception as exc:
                return [], [], f"executor error: {exc}"
            if not ok:
                return [], [], reason
            if call.get("name") in MUTATING_TOOLS:
                args = call.get("args") or {}
                body = args.get("content", args.get("source"))
                if body is not None:
                    staged.append(
                        {
                            "path": args["path"],
                            "action": "modify",
                            "source": body,
                        }
                    )
            else:
                pending.append(call)
        return staged, pending, None

    def _execute_on_temp(self, call: dict[str, Any], temp: Path | None) -> tuple[bool, str]:
        self.state.advance(Phase.EXECUTE_IN_SANDBOX)
        snapshot = self.state.snapshot()
        snapshot["worktree"] = str(temp) if temp is not None else None
        try:
            if self.tool_executor is None:
                self.hooks.emit("after_tool_call", request=call, result={"status": "authorized"})
                self.state.advance(Phase.OBSERVE_RESULT)
                return True, "ok"
            ok, reason = self.tool_executor(call, snapshot)
        except Exception as exc:
            ok, reason = False, f"executor error: {exc}"
        self.hooks.emit(
            "after_tool_call",
            request=call,
            result={"status": "ok" if ok else "error", "reason": reason},
        )
        self.state.advance(Phase.OBSERVE_RESULT)
        return ok, reason

    def authorize_and_maybe_execute(
        self, call: dict[str, Any], execute: bool = True
    ) -> tuple[bool, str]:
        self.state.advance(Phase.AUTHORIZE_TOOL_CALL)
        self.hooks.emit("before_tool_call", request=call, state=self.state.snapshot())
        try:
            ok, reason = authorize_tool(call, self.contract, self.state.snapshot())
        except Exception as exc:
            return False, f"executor error: {exc}"
        if not ok:
            return False, reason
        if not execute or call.get("name") in MUTATING_TOOLS:
            self.hooks.emit("after_tool_call", request=call, result={"status": "authorized"})
            return True, "ok"
        return self._execute_on_temp(call, None)

    def _persist(
        self,
        proposal_sha: str,
        gates: dict[str, str],
        decision: str,
        reasons: list[str],
        parsed: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if decision != "ACCEPT":
            self.state.write_authorized = False
            self.state.note_failure("|".join(reasons) or decision)
            if self.state.identical_failures >= 2:
                self.hooks.emit("on_repeated_failure", state=self.state.snapshot())
                decision = "HALT"
                self.state.advance(Phase.HALT)
            elif decision == "HALT":
                self.state.advance(Phase.HALT)
            else:
                self.state.advance(Phase.RETRY)
        record = make_record(
            self.state.run_id,
            self.state.attempt,
            proposal_sha,
            self.contract["contract_id"],
            gates,
            decision,
            reasons,
            content_sha256=content_sha256(parsed) if parsed else None,
            kind="candidate" if parsed and is_candidate(parsed) else "edit",
        )
        record.write(self.evidence_dir)
        self.records.append(record.payload)
        return record.payload

    def _halt_record(self, sha: str, reason: str) -> dict[str, Any]:
        gates = {
            "parse_compile": "BLOCKED",
            "scope": "BLOCKED",
            "secrets": "BLOCKED",
            "injection": "BLOCKED",
            "contract_preview": "BLOCKED",
            "retry_policy": "FAIL",
        }
        return self._persist(
            sha if len(sha) == 64 else "0" * 64,
            gates,
            "HALT",
            [reason],
            None,
        )
