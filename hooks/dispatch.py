#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


READ_TOOLS = {"Read", "Grep", "Glob", "read_file", "list_files"}
PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$")
MOVE_PATH = re.compile(r"^\*\*\* Move to: (.+)$")
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
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "decision": {"behavior": "deny", "message": reason},
            }
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


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
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(body)


def _state_path(payload: dict[str, Any]) -> Path:
    return _run_dir(payload) / "state.json"


def _read_state(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_state_path(payload).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {"turns": 0, "accepted_paths": []}
    return value if isinstance(value, dict) else {"turns": 0, "accepted_paths": []}


def _write_state(payload: dict[str, Any], state: dict[str, Any]) -> None:
    path = _state_path(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _contract_path(payload: dict[str, Any]) -> Path:
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("cwd is missing")
    return Path(cwd) / ".harness" / "runtime" / "active-contract.json"


def _load_contract(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(_contract_path(payload).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        raise ValueError("valid active contract is required") from exc
    required_lists = ("allowed_paths", "allowed_tools", "allowed_commands", "oracles")
    if not isinstance(value, dict) or not isinstance(value.get("contract_id"), str):
        raise ValueError("valid active contract is required")
    if any(not isinstance(value.get(key), list) for key in required_lists):
        raise ValueError("valid active contract is required")
    budget = value.get("budget")
    if not isinstance(budget, dict):
        raise ValueError("valid active contract is required")
    minima = {"max_files": 0, "max_turns": 1, "max_retries": 0, "timeout_s": 1}
    for key, minimum in minima.items():
        if not isinstance(budget.get(key), int) or budget[key] < minimum:
            raise ValueError("valid active contract is required")
    return value


def _normal_path(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip() or Path(raw).is_absolute():
        return None
    parts = raw.replace("\\", "/").rstrip("/").split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


def _in_scope(path: str, allowed: list[Any]) -> bool:
    for item in allowed:
        root = _normal_path(item) if item != "." else "."
        if root == "." or root and (path == root or path.startswith(root.rstrip("/") + "/")):
            return True
    return False


def _patch_paths(command: Any) -> list[str]:
    if not isinstance(command, str) or not command.startswith("*** Begin Patch\n"):
        raise ValueError("apply_patch command is malformed")
    paths: list[str] = []
    for line in command.splitlines():
        match = PATCH_PATH.match(line) or MOVE_PATH.match(line)
        if match:
            path = _normal_path(match.group(1))
            if path is None:
                raise ValueError("apply_patch contains an unsafe path")
            paths.append(path)
    if not paths:
        raise ValueError("apply_patch contains no file operation")
    return paths


def _gate(payload: dict[str, Any], contract: dict[str, Any]) -> tuple[bool, str, list[str]]:
    name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(name, str) or not isinstance(tool_input, dict):
        return False, "native tool_name and tool_input are required", []
    state = _read_state(payload)
    if state.get("turns", 0) > contract["budget"]["max_turns"]:
        return False, "turn budget exhausted", []
    if name == "Bash":
        command = tool_input.get("command")
        allowed = contract["allowed_commands"]
        ok = "run_command" in contract["allowed_tools"] and command in allowed
        return ok, "command not allow-listed" if not ok else "ok", []
    if name == "apply_patch":
        if "write_file" not in contract["allowed_tools"]:
            return False, "write_file is not allow-listed", []
        try:
            paths = _patch_paths(tool_input.get("command"))
        except ValueError as exc:
            return False, str(exc), []
        if any(not _in_scope(path, contract["allowed_paths"]) for path in paths):
            return False, "apply_patch path out of scope", paths
        touched = set(state.get("accepted_paths") or []) | set(paths)
        if len(touched) > contract["budget"]["max_files"]:
            return False, "file budget exhausted", paths
        if SECRET.search(tool_input["command"]):
            return False, "secret pattern detected", paths
        return True, "ok", paths
    if name in READ_TOOLS:
        return "read_file" in contract["allowed_tools"], "read_file is not allow-listed", []
    return False, f"tool {name} is not allow-listed", []


def _pre_tool(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        contract = _load_contract(payload)
        ok, reason, paths = _gate(payload, contract)
    except ValueError as exc:
        if payload.get("tool_name") in READ_TOOLS:
            return {}
        return _deny(event, str(exc))
    if not ok:
        return _deny(event, reason)
    if event == "PermissionRequest":
        return {}
    tool_id = _safe_component(payload.get("tool_use_id"))
    proposal = {
        "information_state": "VERIFIED",
        "session_id": payload.get("session_id"),
        "turn_id": payload.get("turn_id"),
        "tool_use_id": payload.get("tool_use_id"),
        "tool_name": payload.get("tool_name"),
        "tool_input": payload.get("tool_input"),
        "proposal_sha256": _canonical_hash({
            "tool_name": payload.get("tool_name"),
            "tool_use_id": payload.get("tool_use_id"),
            "tool_input": payload.get("tool_input"),
        }),
        "contract_id": contract["contract_id"],
        "decision": "ACCEPT",
    }
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
    record = {
        "information_state": "OBSERVED",
        "session_id": payload.get("session_id"),
        "turn_id": payload.get("turn_id"),
        "tool_use_id": payload.get("tool_use_id"),
        "tool_name": payload.get("tool_name"),
        "tool_input": payload.get("tool_input"),
        "tool_response": payload.get("tool_response"),
    }
    try:
        contract = _load_contract(payload)
        record["contract_id"] = contract["contract_id"]
        proposal_path = _run_dir(payload) / f"{tool_id}.proposal.json"
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        record["proposal_sha256"] = proposal["proposal_sha256"]
    except (ValueError, FileNotFoundError, json.JSONDecodeError, KeyError):
        record["contract_id"] = None
    try:
        _write_once(_run_dir(payload) / f"{tool_id}.result.json", record)
    except FileExistsError:
        return {"decision": "block", "reason": "duplicate tool result refused"}
    return {}


def _lifecycle(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    if event == "UserPromptSubmit":
        state = _read_state(payload)
        state["turns"] = int(state.get("turns", 0)) + 1
        state["last_prompt_sha256"] = _canonical_hash(payload.get("prompt", ""))
        _write_state(payload, state)
    marker = {
        "information_state": "OBSERVED",
        "event": event,
        "session_id": payload.get("session_id"),
        "turn_id": payload.get("turn_id"),
    }
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
        guarded = event in {"PreToolUse", "PermissionRequest"}
        if guarded:
            output = _deny(event, f"hook failure: {exc}")
        elif event == "PostToolUse":
            output = {"decision": "block", "reason": f"evidence failure: {exc}"}
        else:
            output = {}
    _emit(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
