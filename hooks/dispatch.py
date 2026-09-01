#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(os.environ.get("PLUGIN_ROOT", Path(__file__).resolve().parents[1]))
REFERENCE = PLUGIN_ROOT / "skills" / "bounded-runtime-harness" / "assets" / "reference"
sys.path.insert(0, str(REFERENCE))

from brv.contract import ContractValidationError, load_contract  # noqa: E402
from brv.predicates import (  # noqa: E402
    count_new_files,
    grows_public_exports,
    introduces_version_bump,
    net_line_delta,
    paths_in_scope,
    touches_multiple_files,
)


READ_TOOLS = {"Read", "Grep", "Glob", "read_file", "list_files"}
PATCH_HEADER = re.compile(r"^\*\*\* (Add|Update|Delete) File: (.+)$")
MOVE_HEADER = re.compile(r"^\*\*\* Move to: (.+)$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
SECRET = re.compile(
    r"AKIA[0-9A-Z]{16}|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----|"
    r"(?:api[_-]?key|secret_key|password)\s*[:=]\s*['\"][^'\"]+['\"]",
    re.IGNORECASE,
)


def _emit(value: dict[str, Any]) -> None:
    if value:
        sys.stdout.write(json.dumps(value, separators=(",", ":")))


def _deny(event: str, reason: str) -> dict[str, Any]:
    if event == "PermissionRequest":
        return {"hookSpecificOutput": {"hookEventName": event, "decision": {
            "behavior": "deny", "message": reason,
        }}}
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}


def _canonical_hash(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _safe_component(value: Any) -> str:
    text = str(value or "missing")
    return text if SAFE_ID.fullmatch(text) else _canonical_hash(text)


def _data_root() -> Path:
    raw = os.environ.get("PLUGIN_DATA") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not raw:
        raise ValueError("PLUGIN_DATA is unavailable")
    return Path(raw)


def _run_dir(payload: dict[str, Any]) -> Path:
    return _data_root() / "runs" / _safe_component(payload.get("session_id"))


def _write_once(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(body)


def _state_path(payload: dict[str, Any]) -> Path:
    return _run_dir(payload) / "state.json"


def _read_state(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_state_path(payload).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"turns": 0, "accepted_paths": []}
    if not isinstance(value, dict):
        raise ValueError("runtime state is invalid")
    return value


def _write_state(payload: dict[str, Any], state: dict[str, Any]) -> None:
    path = _state_path(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _load_contract(payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ContractValidationError("valid active contract is required: cwd is missing")
    schema = PLUGIN_ROOT / "skills" / "bounded-runtime-harness" / "assets" / "schemas" / "contract.schema.json"
    value, body = load_contract(
        Path(cwd) / ".harness" / "runtime" / "active-contract.json", schema,
    )
    return value, hashlib.sha256(body).hexdigest()


def _patch_proposal(command: Any) -> dict[str, Any]:
    if not isinstance(command, str) or not command.startswith("*** Begin Patch\n"):
        raise ValueError("apply_patch command is malformed")
    edits: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    body: list[str] = []
    action_map = {"Add": "create", "Update": "update", "Delete": "delete"}
    for line in command.splitlines()[1:]:
        match = PATCH_HEADER.match(line)
        if match:
            if current is not None:
                current["unified_diff"] = "\n".join(body)
                edits.append(current)
            current = {"action": action_map[match.group(1)], "path": match.group(2)}
            body = []
            continue
        moved = MOVE_HEADER.match(line)
        if moved and current is not None:
            current["move_to"] = moved.group(1)
            continue
        if line == "*** End Patch":
            break
        if current is not None:
            body.append(line)
    if current is not None:
        current["unified_diff"] = "\n".join(body)
        edits.append(current)
    if not edits:
        raise ValueError("apply_patch contains no file operation")
    return {"kind": "edit", "edits": edits, "tool_calls": []}


def _read_paths(name: str, tool_input: dict[str, Any]) -> list[str]:
    raw = tool_input.get("path", tool_input.get("file_path"))
    if raw is None and name in {"Grep", "Glob", "list_files"}:
        raw = "."
    if not isinstance(raw, str):
        raise ValueError("read path is required")
    return [raw]


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _paths_out_of_scope(paths: list[str], allowed: list[str], cwd: Path) -> list[str]:
    lexical = paths_in_scope(paths, allowed)
    if lexical:
        return lexical
    root = cwd.resolve()
    allowed_roots = [
        candidate
        for raw in allowed
        if not paths_in_scope([raw], ["."])
        for candidate in [(root / raw).resolve()]
        if _is_within(candidate, root)
    ]
    if not allowed_roots:
        return list(paths)
    return [
        raw
        for raw in paths
        if not any(
            _is_within((root / raw).resolve(), allowed_root)
            for allowed_root in allowed_roots
        )
    ]


def _predicate_failure(
    proposal: dict[str, Any], contract: dict[str, Any], cwd: Path, prior_paths: set[str],
) -> str | None:
    enabled = contract["predicates"]
    checks = (
        ("forbid_new_files", count_new_files(proposal, cwd) > 0),
        ("forbid_version_bump", introduces_version_bump(proposal)),
        ("forbid_public_export_growth", grows_public_exports(proposal, cwd)),
        ("net_non_positive_lines", net_line_delta(proposal, cwd) > 0),
        ("one_file_scope", touches_multiple_files(proposal) or len(prior_paths | set(
            edit["path"] for edit in proposal["edits"]
        )) > 1),
    )
    return next((name for name, failed in checks if enabled[name] and failed), None)


def _gate(payload: dict[str, Any], contract: dict[str, Any]) -> tuple[bool, str, list[str]]:
    name, tool_input = payload.get("tool_name"), payload.get("tool_input")
    if not isinstance(name, str) or not isinstance(tool_input, dict):
        return False, "native tool_name and tool_input are required", []
    state = _read_state(payload)
    if state.get("turns", 0) > contract["budget"]["max_turns"]:
        return False, "turn budget exhausted", []
    allowed_paths = [path.rstrip("/") or "." for path in contract["allowed_paths"]]
    if name == "Bash":
        command = tool_input.get("command")
        ok = "run_command" in contract["allowed_tools"] and command in contract["allowed_commands"]
        return ok, "command not allow-listed" if not ok else "ok", []
    if name == "apply_patch":
        if "write_file" not in contract["allowed_tools"]:
            return False, "write_file is not allow-listed", []
        try:
            proposal = _patch_proposal(tool_input.get("command", tool_input.get("patch")))
        except ValueError as exc:
            return False, str(exc), []
        paths = [edit["path"] for edit in proposal["edits"]]
        paths += [edit["move_to"] for edit in proposal["edits"] if "move_to" in edit]
        if _paths_out_of_scope(paths, allowed_paths, Path(payload["cwd"])):
            return False, "apply_patch path out of scope", paths
        prior = set(state.get("accepted_paths") or [])
        if len(prior | set(paths)) > contract["budget"]["max_files"]:
            return False, "file budget exhausted", paths
        failure = _predicate_failure(proposal, contract, Path(payload["cwd"]), prior)
        if failure:
            return False, f"{failure} predicate rejected proposal", paths
        command = tool_input.get("command", tool_input.get("patch", ""))
        if SECRET.search(command):
            return False, "secret pattern detected", paths
        return True, "ok", paths
    if name in READ_TOOLS:
        if "read_file" not in contract["allowed_tools"]:
            return False, "read_file is not allow-listed", []
        try:
            paths = _read_paths(name, tool_input)
        except ValueError as exc:
            return False, str(exc), []
        return (False, "read path out of scope", paths) if _paths_out_of_scope(paths, allowed_paths, Path(payload["cwd"])) else (True, "ok", [])
    return False, f"tool {name} is not allow-listed", []


def _pre_tool(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        contract, contract_sha = _load_contract(payload)
        ok, reason, paths = _gate(payload, contract)
    except (ContractValidationError, ValueError, OSError, json.JSONDecodeError) as exc:
        return _deny(event, str(exc))
    if not ok:
        return _deny(event, reason)
    if event == "PermissionRequest":
        return {}
    request = {key: payload.get(key) for key in ("tool_name", "tool_use_id", "tool_input")}
    proposal = {
        "information_state": "VERIFIED", "session_id": payload.get("session_id"),
        "turn_id": payload.get("turn_id"), **request,
        "proposal_sha256": _canonical_hash(request), "contract_id": contract["contract_id"],
        "contract_sha256": contract_sha, "decision": "ACCEPT",
    }
    tool_id = _safe_component(payload.get("tool_use_id"))
    try:
        _write_once(_run_dir(payload) / f"{tool_id}.proposal.json", proposal)
    except FileExistsError:
        return _deny(event, "duplicate tool proposal refused")
    if paths:
        state = _read_state(payload)
        state["accepted_paths"] = sorted(set(state.get("accepted_paths") or []) | set(paths))
        _write_state(payload, state)
    return {}


def _post_tool(payload: dict[str, Any]) -> dict[str, Any]:
    tool_id = _safe_component(payload.get("tool_use_id"))
    proposal_path = _run_dir(payload) / f"{tool_id}.proposal.json"
    proposal: dict[str, Any] | None = None
    proposal_error: str | None = None
    try:
        candidate = json.loads(proposal_path.read_text(encoding="utf-8"))
        if isinstance(candidate, dict):
            proposal = candidate
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        proposal_error = f"{type(exc).__name__}: {exc}"
    request = {key: payload.get(key) for key in ("tool_name", "tool_use_id", "tool_input")}
    proposal_sha = proposal.get("proposal_sha256") if proposal else None
    proposal_valid = bool(
        proposal
        and proposal.get("information_state") == "VERIFIED"
        and proposal.get("decision") == "ACCEPT"
        and isinstance(proposal.get("contract_id"), str)
        and isinstance(proposal.get("contract_sha256"), str)
        and proposal_sha == _canonical_hash(request)
    )
    provenance = "PASS" if proposal_valid else "FAIL"
    record = {
        "information_state": "OBSERVED", "session_id": payload.get("session_id"),
        "turn_id": payload.get("turn_id"), **request,
        "tool_response": payload.get("tool_response"), "provenance_verdict": provenance,
        "contract_id": proposal.get("contract_id") if proposal else None,
        "contract_sha256": proposal.get("contract_sha256") if proposal else None,
        "proposal_sha256": proposal.get("proposal_sha256") if proposal else None,
        "provenance_error": proposal_error,
    }
    try:
        _write_once(_run_dir(payload) / f"{tool_id}.result.json", record)
    except FileExistsError:
        return {"decision": "block", "reason": "duplicate tool result refused"}
    if provenance == "FAIL":
        return {"decision": "block", "reason": "tool result provenance mismatch"}
    return {}


def _lifecycle(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    if event == "UserPromptSubmit":
        state = _read_state(payload)
        state["turns"] = int(state.get("turns", 0)) + 1
        state["last_prompt_sha256"] = _canonical_hash(payload.get("prompt", ""))
        _write_state(payload, state)
    marker = {"information_state": "OBSERVED", "event": event,
              "session_id": payload.get("session_id"), "turn_id": payload.get("turn_id")}
    name = f"{event}-{_safe_component(payload.get('turn_id') or payload.get('source') or payload.get('reason'))}.json"
    try:
        _write_once(_run_dir(payload) / name, marker)
    except FileExistsError:
        return {}
    return {}


def main() -> int:
    event = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or payload.get("hook_event_name") != event:
            raise ValueError("hook event mismatch")
        if event in {"PreToolUse", "PermissionRequest"}:
            output = _pre_tool(event, payload)
        elif event == "PostToolUse":
            output = _post_tool(payload)
        elif event in {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"}:
            output = _lifecycle(event, payload)
        else:
            raise ValueError("unsupported hook event")
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        if event in {"PreToolUse", "PermissionRequest"}:
            output = _deny(event, f"hook failure: {exc}")
        elif event == "PostToolUse":
            output = {"decision": "block", "reason": f"evidence failure: {exc}"}
        else:
            output = {}
    _emit(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
