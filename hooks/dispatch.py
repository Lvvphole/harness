"""Codex lifecycle hook dispatcher.

Receives Codex events on stdin, routes them through the bounded runtime
controller, and writes Codex-compatible responses to stdout.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE = REPO_ROOT / "skills" / "bounded-runtime-harness" / "assets" / "reference"
sys.path.insert(0, str(REFERENCE))

from brv.controller import Controller
from brv.gates import authorize_tool
from brv.hooks import HookRegistry
from brv.state import Phase, RunState

from tokens import mint_token, validate_token

EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "Stop",
    "SessionEnd",
)

STATE_FILE = ".harness/runs/codex-session-state.json"
EVIDENCE_DIR = ".harness/runs"


def _state_path() -> Path:
    return REPO_ROOT / STATE_FILE


def _evidence_path() -> Path:
    return REPO_ROOT / EVIDENCE_DIR


def _load_state() -> dict[str, Any]:
    path = _state_path()
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _save_state(state: dict[str, Any]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def _load_contract() -> dict[str, Any]:
    contracts_dir = REPO_ROOT / ".harness" / "contracts"
    for p in sorted(contracts_dir.glob("*.md")):
        return {
            "contract_id": p.stem,
            "task_type": "codex-session",
            "allowed_paths": ["src"],
            "allowed_tools": ["read_file", "write_file", "run_command", "run_oracle"],
            "allowed_commands": [],
            "oracles": [],
            "budget": {"max_files": 16, "max_turns": 20, "max_retries": 2, "timeout_s": 120},
            "predicates": {},
        }
    return {
        "contract_id": "default",
        "task_type": "codex-session",
        "allowed_paths": ["src"],
        "allowed_tools": ["read_file", "write_file", "run_command"],
        "allowed_commands": [],
        "oracles": [],
        "budget": {"max_files": 16, "max_turns": 20, "max_retries": 2, "timeout_s": 120},
        "predicates": {},
    }


def _respond(decision: str, reason: str = "") -> None:
    response: dict[str, Any] = {"decision": decision}
    if reason:
        response["reason"] = reason
    json.dump(response, sys.stdout)
    sys.stdout.write("\n")
    sys.stdout.flush()


def handle_session_start(payload: dict[str, Any]) -> None:
    contract = _load_contract()
    session_id = payload.get("session_id", "codex-session")
    state = {
        "session_id": session_id,
        "contract": contract,
        "turn": 0,
        "write_authorized": False,
        "files_touched": 0,
        "proposal_sha": None,
        "active_token": None,
        "permitted_tools": contract["allowed_tools"],
        "permitted_paths": contract["allowed_paths"],
    }
    _save_state(state)
    _respond("approve")


def handle_user_prompt_submit(payload: dict[str, Any]) -> None:
    state = _load_state()
    state["turn"] = state.get("turn", 0) + 1
    state["write_authorized"] = False
    state["proposal_sha"] = None
    state["active_token"] = None
    _save_state(state)
    _respond("approve")


def handle_pre_tool_use(payload: dict[str, Any]) -> None:
    state = _load_state()
    tool_name = payload.get("tool", {}).get("name", "")
    tool_args = payload.get("tool", {}).get("args", {})
    tool_path = tool_args.get("path")

    contract = state.get("contract", {})
    run_state = {
        "write_authorized": state.get("write_authorized", False),
        "turns": state.get("turn", 0),
        "files_touched": state.get("files_touched", 0),
    }
    call = {"name": tool_name, "args": tool_args}
    ok, reason = authorize_tool(call, contract, run_state)
    if not ok:
        _respond("deny", reason)
        return

    if tool_name == "write_file":
        token = state.get("active_token")
        if token is None:
            _respond("deny", "write not authorized by inference gate")
            return
        valid = validate_token(
            token,
            state.get("session_id", ""),
            contract.get("contract_id", ""),
            state.get("proposal_sha", ""),
            tool_name,
            tool_path,
            state.get("turn", 0),
            state.get("permitted_tools", []),
            state.get("permitted_paths", []),
        )
        if not valid:
            _respond("deny", "invalid authorization token")
            return

    _respond("approve")


def handle_permission_request(payload: dict[str, Any]) -> None:
    state = _load_state()
    tool_name = payload.get("tool", {}).get("name", "")
    tool_args = payload.get("tool", {}).get("args", {})

    contract = state.get("contract", {})
    run_state = {
        "write_authorized": state.get("write_authorized", False),
        "turns": state.get("turn", 0),
        "files_touched": state.get("files_touched", 0),
    }
    call = {"name": tool_name, "args": tool_args}
    ok, reason = authorize_tool(call, contract, run_state)
    if ok:
        _respond("approve")
    else:
        _respond("deny", reason)


def handle_post_tool_use(payload: dict[str, Any]) -> None:
    state = _load_state()
    tool_name = payload.get("tool", {}).get("name", "")
    if tool_name == "write_file":
        state["files_touched"] = state.get("files_touched", 0) + 1
    _save_state(state)
    _respond("approve")


def handle_stop(payload: dict[str, Any]) -> None:
    state = _load_state()
    evidence_dir = _evidence_path()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "event": "Stop",
        "session_id": state.get("session_id", ""),
        "turn": state.get("turn", 0),
        "files_touched": state.get("files_touched", 0),
        "reason": payload.get("reason", ""),
    }
    summary_path = evidence_dir / "codex-stop-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    _respond("approve")


def handle_session_end(payload: dict[str, Any]) -> None:
    state = _load_state()
    evidence_dir = _evidence_path()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "event": "SessionEnd",
        "session_id": state.get("session_id", ""),
        "turn": state.get("turn", 0),
        "files_touched": state.get("files_touched", 0),
        "sealed": True,
    }
    seal_path = evidence_dir / "codex-session-seal.json"
    seal_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
    state_path = _state_path()
    if state_path.exists():
        state_path.unlink()
    _respond("approve")


HANDLERS = {
    "SessionStart": handle_session_start,
    "UserPromptSubmit": handle_user_prompt_submit,
    "PreToolUse": handle_pre_tool_use,
    "PermissionRequest": handle_permission_request,
    "PostToolUse": handle_post_tool_use,
    "Stop": handle_stop,
    "SessionEnd": handle_session_end,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in EVENTS:
        print(json.dumps({"decision": "deny", "reason": f"unknown event: {sys.argv[1] if len(sys.argv) > 1 else '(none)'}"}))
        sys.exit(1)

    event = sys.argv[1]
    raw = sys.stdin.read().strip()
    payload: dict[str, Any] = json.loads(raw) if raw else {}
    HANDLERS[event](payload)


if __name__ == "__main__":
    main()
