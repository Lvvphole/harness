from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .predicates import is_unsafe_path
from .worktree import PatchError, sandbox_path

SCHEMA_VERSION_EDIT = "1.0"
SCHEMA_VERSION_CANDIDATE = "1.1"
ALLOWED_INTENTS = {"edit", "tool", "noop"}
ALLOWED_ACTIONS = {"modify", "create", "delete"}
ALLOWED_TOOLS = {"read_file", "write_file", "run_command", "run_oracle"}
ALLOWED_LANGUAGES = {"python", "json", "text"}
PATH_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./-")


class EnvelopeError(ValueError):
    pass


def _require_relpath(path: Any) -> str:
    if not isinstance(path, str) or not path or any(c not in PATH_OK for c in path):
        raise EnvelopeError("path contains illegal characters")
    if is_unsafe_path(path):
        raise EnvelopeError("path must be a relative sandbox path")
    return path


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def hash_proposal(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def parse_proposal(raw: str | bytes | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        data = raw
    else:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise EnvelopeError(f"proposal is not JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise EnvelopeError("proposal envelope must be an object")
    version = data.get("schema_version")
    if version == SCHEMA_VERSION_CANDIDATE or data.get("kind") == "candidate":
        return _parse_candidate(data)
    if version != SCHEMA_VERSION_EDIT:
        raise EnvelopeError("unsupported schema_version")
    if not data.get("contract_id"):
        raise EnvelopeError("contract_id required")
    if data.get("intent") not in ALLOWED_INTENTS:
        raise EnvelopeError("intent must be edit|tool|noop")
    if "edits" not in data or "tool_calls" not in data:
        raise EnvelopeError("edits and tool_calls required")
    if not isinstance(data["edits"], list) or not isinstance(data["tool_calls"], list):
        raise EnvelopeError("edits and tool_calls must be arrays")
    for edit in data["edits"]:
        if not isinstance(edit, dict):
            raise EnvelopeError("edit must be an object")
        if edit.get("action") not in ALLOWED_ACTIONS:
            raise EnvelopeError("invalid edit action")
        if "path" not in edit or "unified_diff" not in edit:
            raise EnvelopeError("edit requires path and unified_diff")
        _require_relpath(edit.get("path"))
    for call in data["tool_calls"]:
        if not isinstance(call, dict):
            raise EnvelopeError("tool_call must be an object")
        if call.get("name") not in ALLOWED_TOOLS:
            raise EnvelopeError("tool name not in enum")
        if not isinstance(call.get("args"), dict):
            raise EnvelopeError("tool args must be an object")
        if "path" in call["args"]:
            _require_relpath(call["args"]["path"])
    extra = set(data) - {"schema_version", "contract_id", "intent", "edits", "tool_calls", "notes"}
    if extra:
        raise EnvelopeError(f"unknown envelope fields: {sorted(extra)}")
    return data


def _parse_candidate(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("schema_version") != SCHEMA_VERSION_CANDIDATE:
        raise EnvelopeError("candidate requires schema_version 1.1")
    if data.get("kind") != "candidate":
        raise EnvelopeError("kind must be candidate")
    required = ("contract_id", "language", "path", "source")
    for key in required:
        if key not in data:
            raise EnvelopeError(f"{key} required")
    if data["language"] not in ALLOWED_LANGUAGES:
        raise EnvelopeError("language must be python|json|text")
    _require_relpath(data["path"])
    if not isinstance(data["source"], str):
        raise EnvelopeError("source must be a string")
    extra = set(data) - {
        "schema_version",
        "kind",
        "contract_id",
        "language",
        "path",
        "source",
    }
    if extra:
        raise EnvelopeError(f"unknown candidate fields: {sorted(extra)}")
    return data


def is_candidate(parsed: dict[str, Any]) -> bool:
    return parsed.get("kind") == "candidate"


def as_edits(parsed: dict[str, Any], worktree: Path) -> list[dict[str, Any]]:
    if not is_candidate(parsed):
        return list(parsed.get("edits") or [])
    path = parsed["path"]
    try:
        exists = sandbox_path(worktree, path).exists()
    except PatchError:
        exists = False
    return [
        {
            "path": path,
            "action": "modify" if exists else "create",
            "source": parsed["source"],
        }
    ]


def content_sha256(parsed: dict[str, Any]) -> str | None:
    if not is_candidate(parsed):
        return None
    return hashlib.sha256(parsed["source"].encode("utf-8")).hexdigest()


def load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
