from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any


VERSION_RE = re.compile(
    r"""(["']?version["']?\s*[:=]\s*["']?\d+\.\d+|^\s*version\s*=\s*["']?\d+\.\d+)""",
    re.IGNORECASE | re.MULTILINE,
)
EXPORT_RE = re.compile(r"^\s*export\s+", re.MULTILINE)


def is_unsafe_path(raw: str) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return True
    if "\x00" in raw or raw.startswith("~"):
        return True
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        return True
    if Path(raw).is_absolute():
        return True
    parts = [part for part in normalized.split("/") if part not in ("", ".")]
    if not parts:
        return True
    if any(part == ".." for part in parts):
        return True
    if ":" in parts[0]:
        return True
    return False


def paths_in_scope(paths: list[str], allowed: list[str]) -> list[str]:
    out = []
    for raw in paths:
        if is_unsafe_path(raw):
            out.append(raw)
            continue
        p = raw.replace("\\", "/").lstrip("./")
        ok = any(p == a or p.startswith(a.rstrip("/") + "/") or a == "." for a in allowed)
        if not ok:
            out.append(p)
    return out


def _is_candidate(proposal: dict[str, Any]) -> bool:
    return proposal.get("kind") == "candidate"


def proposed_paths(proposal: dict[str, Any]) -> list[str]:
    if _is_candidate(proposal):
        return [proposal["path"]]
    paths = [e["path"] for e in proposal.get("edits", [])]
    for call in proposal.get("tool_calls", []):
        args = call.get("args") or {}
        if "path" in args:
            paths.append(args["path"])
    return paths


def _safe_target(worktree: Path | None, rel: str):
    if worktree is None or is_unsafe_path(rel):
        return None
    from .worktree import PatchError, sandbox_path

    try:
        return sandbox_path(worktree, rel)
    except (PatchError, OSError):
        return None


def _safe_exists(worktree: Path | None, rel: str) -> bool:
    target = _safe_target(worktree, rel)
    try:
        return bool(target and target.exists() and target.is_file())
    except OSError:
        return False


def _safe_existing_text(worktree: Path | None, rel: str) -> str | None:
    target = _safe_target(worktree, rel)
    if target is None:
        return None
    try:
        if not target.exists() or not target.is_file():
            return None
        return target.read_text()
    except (OSError, UnicodeDecodeError):
        return None


def count_new_files(proposal: dict[str, Any], worktree: Path) -> int:
    if _is_candidate(proposal):
        return 0 if _safe_exists(worktree, proposal["path"]) else 1
    n = 0
    for edit in proposal.get("edits", []):
        if edit["action"] == "create" and not _safe_exists(worktree, edit["path"]):
            n += 1
    return n


def touches_multiple_files(proposal: dict[str, Any]) -> bool:
    if _is_candidate(proposal):
        return False
    return len({e["path"] for e in proposal.get("edits", [])}) > 1


def introduces_version_bump(proposal: dict[str, Any]) -> bool:
    if _is_candidate(proposal):
        return bool(VERSION_RE.search(proposal.get("source") or ""))
    return any(VERSION_RE.search(e.get("unified_diff") or "") for e in proposal.get("edits", []))


def _python_public_names(source: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
    return names


def grows_public_exports(proposal: dict[str, Any], worktree: Path | None = None) -> bool:
    if _is_candidate(proposal):
        new = proposal.get("source") or ""
        old = _safe_existing_text(worktree, proposal["path"]) or ""
        if proposal.get("language") == "python":
            return len(_python_public_names(new) - _python_public_names(old)) > 0
        return len(EXPORT_RE.findall(new)) > len(EXPORT_RE.findall(old))
    for edit in proposal.get("edits", []):
        diff = edit.get("unified_diff") or ""
        added = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        removed = [ln[1:] for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---")]
        added_ex = sum(1 for ln in added if EXPORT_RE.search(ln))
        removed_ex = sum(1 for ln in removed if EXPORT_RE.search(ln))
        if added_ex > removed_ex:
            return True
    return False


def net_line_delta(proposal: dict[str, Any], worktree: Path | None = None) -> int:
    if _is_candidate(proposal):
        new_n = len((proposal.get("source") or "").splitlines())
        old = _safe_existing_text(worktree, proposal["path"]) or ""
        return new_n - len(old.splitlines()) if old else new_n
    delta = 0
    for edit in proposal.get("edits", []):
        diff = edit.get("unified_diff") or ""
        for ln in diff.splitlines():
            if ln.startswith("+") and not ln.startswith("+++"):
                delta += 1
            elif ln.startswith("-") and not ln.startswith("---"):
                delta -= 1
    return delta
