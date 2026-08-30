from __future__ import annotations

from pathlib import Path
from typing import Any

from .envelope import EnvelopeError, is_candidate, parse_proposal
from .languages import LanguageError, parse_source
from .predicates import (
    count_new_files,
    grows_public_exports,
    introduces_version_bump,
    net_line_delta,
    paths_in_scope,
    proposed_paths,
    touches_multiple_files,
)
from .secrets import find_secret_hits
from .worktree import PatchError, apply_unified_diff

GateStatus = str  # PASS | FAIL | BLOCKED

_SUFFIX_LANGUAGE = {
    ".py": "python",
    ".json": "json",
}


def _status(ok: bool, blocked: bool = False) -> GateStatus:
    if blocked:
        return "BLOCKED"
    return "PASS" if ok else "FAIL"


def _language_for(path: str) -> str | None:
    return _SUFFIX_LANGUAGE.get(Path(path).suffix)


def _resulting_source(edit: dict[str, Any], worktree: Path) -> str | None:
    if edit.get("action") == "delete":
        return None
    if "source" in edit:
        return edit["source"]
    existing = ""
    target = worktree / edit["path"]
    if target.exists():
        existing = target.read_text()
    return apply_unified_diff(existing, edit.get("unified_diff") or "")


def evaluate_inference(
    raw_proposal: str | bytes | dict[str, Any],
    contract: dict[str, Any],
    worktree: Path,
    attempt: int,
    known_secrets: set[str] | None = None,
) -> tuple[dict[str, GateStatus], list[str], dict[str, Any] | None]:
    reasons: list[str] = []
    parsed: dict[str, Any] | None = None
    try:
        parsed = parse_proposal(raw_proposal)
        parse_compile = "PASS"
    except EnvelopeError as exc:
        parse_compile = "FAIL"
        reasons.append(f"parse_compile: {exc}")

    if parsed is None:
        gates = {
            "parse_compile": parse_compile,
            "scope": "BLOCKED",
            "secrets": "BLOCKED",
            "injection": "BLOCKED",
            "contract_preview": "BLOCKED",
            "retry_policy": _status(attempt <= contract["budget"]["max_retries"]),
        }
        return gates, reasons, None

    if parsed["contract_id"] != contract["contract_id"]:
        reasons.append("parse_compile: contract_id mismatch")
        parse_compile = "FAIL"

    if parse_compile == "PASS":
        try:
            if is_candidate(parsed):
                parse_source(parsed["language"], parsed["source"])
            else:
                for edit in parsed.get("edits") or []:
                    language = _language_for(edit.get("path") or "")
                    if language is None:
                        continue
                    source = _resulting_source(edit, worktree)
                    if source is None:
                        continue
                    parse_source(language, source)
        except (LanguageError, PatchError) as exc:
            parse_compile = "FAIL"
            reasons.append(f"parse_compile: {exc}")

    out_of_scope = paths_in_scope(proposed_paths(parsed), contract["allowed_paths"])
    scope = _status(not out_of_scope)
    if out_of_scope:
        reasons.append(f"scope: {out_of_scope}")

    blob = parsed["source"] if is_candidate(parsed) else str(parsed)
    secret_hits = find_secret_hits(blob, known_secrets)
    secrets = _status(not secret_hits)
    if secret_hits:
        reasons.append("secrets: pattern or entropy hit")

    injection = "PASS"

    preds = contract["predicates"]
    preview_fail = []
    if preds.get("forbid_new_files") and count_new_files(parsed, worktree):
        preview_fail.append("INV-1 new files")
    if preds.get("one_file_scope") and touches_multiple_files(parsed):
        preview_fail.append("INV-7 multi-file")
    if preds.get("forbid_version_bump") and introduces_version_bump(parsed):
        preview_fail.append("INV-5 version bump")
    if preds.get("forbid_public_export_growth") and grows_public_exports(parsed, worktree):
        preview_fail.append("INV-2 export growth")
    if preds.get("net_non_positive_lines") and net_line_delta(parsed, worktree) > 0:
        preview_fail.append("INV-3 line growth")
    contract_preview = _status(not preview_fail)
    reasons.extend(f"contract_preview: {p}" for p in preview_fail)

    retry_policy = _status(attempt <= contract["budget"]["max_retries"])
    if retry_policy != "PASS":
        reasons.append("retry_policy: cap exceeded")

    gates = {
        "parse_compile": parse_compile,
        "scope": scope,
        "secrets": secrets,
        "injection": injection,
        "contract_preview": contract_preview,
        "retry_policy": retry_policy,
    }
    return gates, reasons, parsed


def decide(gates: dict[str, GateStatus]) -> str:
    if any(v == "BLOCKED" for k, v in gates.items() if k != "retry_policy"):
        if gates.get("retry_policy") == "FAIL":
            return "HALT"
        return "REJECT"
    if gates.get("retry_policy") == "FAIL":
        return "HALT"
    if all(v == "PASS" for v in gates.values()):
        return "ACCEPT"
    return "REJECT"


def authorize_tool(call: dict[str, Any], contract: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
    name = call.get("name")
    if name not in contract["allowed_tools"]:
        return False, f"tool {name} not allow-listed"
    args = call.get("args") or {}
    if name in {"read_file", "write_file"} and "path" in args:
        bad = paths_in_scope([args["path"]], contract["allowed_paths"])
        if bad:
            return False, f"path out of scope: {bad}"
    if name == "write_file" and not state.get("write_authorized"):
        return False, "write not authorized by inference gate"
    if name == "run_command":
        cmd = args.get("cmd") or ""
        allowed = contract.get("allowed_commands") or []
        if allowed and cmd not in allowed:
            return False, "command not allow-listed"
    if state.get("turns", 0) >= contract["budget"]["max_turns"]:
        return False, "turn budget exhausted"
    if state.get("files_touched", 0) > contract["budget"]["max_files"]:
        return False, "file budget exhausted"
    return True, "ok"
