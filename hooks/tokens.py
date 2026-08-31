from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def _derive_key(session_id: str, contract_id: str) -> bytes:
    return hashlib.sha256(f"{session_id}:{contract_id}".encode()).digest()


def mint_token(
    session_id: str,
    contract_id: str,
    proposal_sha: str,
    permitted_tools: list[str],
    permitted_paths: list[str],
    turn: int,
) -> str:
    key = _derive_key(session_id, contract_id)
    payload = json.dumps(
        {
            "session_id": session_id,
            "contract_id": contract_id,
            "proposal_sha": proposal_sha,
            "permitted_tools": sorted(permitted_tools),
            "permitted_paths": sorted(permitted_paths),
            "turn": turn,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    mac = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    return mac


def validate_token(
    token: str,
    session_id: str,
    contract_id: str,
    proposal_sha: str,
    tool_name: str,
    tool_path: str | None,
    turn: int,
    permitted_tools: list[str],
    permitted_paths: list[str],
) -> bool:
    expected = mint_token(
        session_id, contract_id, proposal_sha,
        permitted_tools, permitted_paths, turn,
    )
    if not hmac.compare_digest(token, expected):
        return False
    if tool_name not in permitted_tools:
        return False
    if tool_path is not None and not any(
        tool_path == p or tool_path.startswith(p.rstrip("/") + "/")
        for p in permitted_paths
    ):
        return False
    return True
