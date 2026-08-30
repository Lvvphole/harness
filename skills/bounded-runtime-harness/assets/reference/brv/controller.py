from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .envelope import as_edits, content_sha256, hash_proposal, is_candidate
from .evidence import make_record
from .gates import authorize_tool, decide, evaluate_inference
from .hooks import HookRegistry
from .state import Phase, RunState
from .worktree import WorktreeTransaction


class Controller:
    """Transactional inference-gate controller.

    MODEL OUTPUT
      → PARSE CANDIDATE OR EDIT ENVELOPE
      → LANGUAGE PARSER (AST / reject)
      → APPLY SOURCE TO TEMPORARY WORKTREE
      → RUN SIX GATES
      → ACCEPT: write exact source bytes to real worktree
      → REJECT: discard temporary state and retry
      → HALT: preserve evidence and stop
    """

    def __init__(
        self,
        authoritative: Path,
        contract: dict[str, Any],
        evidence_dir: Path,
        run_id: str = "run-001",
        known_secrets: set[str] | None = None,
        oracle_runner: Callable[[dict[str, Any], Path], bool] | None = None,
    ):
        self.authoritative = Path(authoritative)
        self.contract = contract
        self.evidence_dir = Path(evidence_dir)
        self.known_secrets = known_secrets
        self.oracle_runner = oracle_runner
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

        if decision != "ACCEPT":
            self.state.write_authorized = False
            self.state.note_failure("|".join(reasons) or decision)
            if self.state.identical_failures >= 2:
                self.hooks.emit("on_repeated_failure", state=self.state.snapshot())
                self.state.advance(Phase.HALT)
                record.payload["decision"] = "HALT"
                record.payload["write_authorized"] = False
                return record.payload
            if decision == "HALT":
                self.state.advance(Phase.HALT)
            else:
                self.state.advance(Phase.RETRY)
            return record.payload

        assert parsed is not None
        self.hooks.emit(
            "before_model_output_accepted",
            proposal=parsed,
            sha256=proposal_sha,
            state=self.state.snapshot(),
        )
        edits = as_edits(parsed, self.authoritative)
        with WorktreeTransaction(self.authoritative) as txn:
            txn.bind(proposal_sha, edits)
            txn.apply_to_temp(edits)
            self.hooks.emit("before_state_commit", sha256=proposal_sha)
            txn.commit(proposal_sha)
        self.state.write_authorized = True
        self.state.files_touched += len({e["path"] for e in edits})
        self.hooks.emit("after_mutation", paths=[e["path"] for e in edits])
        self.state.advance(Phase.COMMIT)

        if parsed.get("tool_calls"):
            for call in parsed["tool_calls"]:
                auth_ok, reason = self.authorize_and_maybe_execute(call)
                if not auth_ok:
                    self.state.advance(Phase.BLOCKED)
                    record.payload["decision"] = "HALT"
                    record.payload["write_authorized"] = False
                    record.payload["reasons"].append(reason)
                    return record.payload

        if self.oracle_runner:
            self.state.advance(Phase.RUN_ORACLE)
            ok = self.oracle_runner(self.contract, self.authoritative)
            self.state.advance(Phase.PASS if ok else Phase.FAIL)
        else:
            self.state.advance(Phase.PASS)
        return record.payload

    def authorize_and_maybe_execute(self, call: dict[str, Any]) -> tuple[bool, str]:
        self.state.advance(Phase.AUTHORIZE_TOOL_CALL)
        self.hooks.emit("before_tool_call", request=call, state=self.state.snapshot())
        ok, reason = authorize_tool(call, self.contract, self.state.snapshot())
        if not ok:
            return False, reason
        self.state.advance(Phase.EXECUTE_IN_SANDBOX)
        self.hooks.emit("after_tool_call", request=call, result={"status": "ok"})
        self.state.advance(Phase.OBSERVE_RESULT)
        return True, "ok"

    def _halt_record(self, sha: str, reason: str) -> dict[str, Any]:
        gates = {
            "parse_compile": "BLOCKED",
            "scope": "BLOCKED",
            "secrets": "BLOCKED",
            "injection": "BLOCKED",
            "contract_preview": "BLOCKED",
            "retry_policy": "FAIL",
        }
        record = make_record(
            self.state.run_id,
            max(self.state.attempt, 1),
            sha if len(sha) == 64 else "0" * 64,
            self.contract["contract_id"],
            gates,
            "HALT",
            [reason],
        )
        record.write(self.evidence_dir)
        self.records.append(record.payload)
        self.state.advance(Phase.HALT)
        return record.payload
