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
PY_PUBLIC_RE = re.compile(r"^(?:async\s+def|def|class)\s+([A-Za-z_]\w*)\b")


def is_unsafe_path(raw: str) -> bool:
    if not isinstance(raw, str) or not raw.strip():
        return True
    if raw.startswith("/") or raw.startswith("\\") or Path(raw).is_absolute():
        return True
    parts = raw.replace("\\", "/").split("/")
    return any(part == ".." for part in parts)


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


def count_new_files(proposal: dict[str, Any], worktree: Path) -> int:
    if _is_candidate(proposal):
        return 0 if (worktree / proposal["path"]).exists() else 1
    n = 0
    for edit in proposal.get("edits", []):
        if edit["action"] == "create" and not (worktree / edit["path"]).exists():
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


def _python_public_diff_names(lines: list[str]) -> set[str]:
    names: set[str] = set()
    for line in lines:
        match = PY_PUBLIC_RE.match(line)
        if match and not match.group(1).startswith("_"):
            names.add(match.group(1))
    return names


def grows_public_exports(proposal: dict[str, Any], worktree: Path | None = None) -> bool:
    if _is_candidate(proposal):
        new = proposal.get("source") or ""
        old = ""
        if worktree is not None:
            target = worktree / proposal["path"]
            if target.exists():
                old = target.read_text()
        if proposal.get("language") == "python":
            return len(_python_public_names(new) - _python_public_names(old)) > 0
        added_ex = len(EXPORT_RE.findall(new))
        removed_ex = len(EXPORT_RE.findall(old))
        return added_ex > removed_ex
    for edit in proposal.get("edits", []):
        diff = edit.get("unified_diff") or ""
        added = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        removed = [ln[1:] for ln in diff.splitlines() if ln.startswith("-") and not ln.startswith("---")]
        if str(edit.get("path", "")).endswith(".py"):
            if _python_public_diff_names(added) - _python_public_diff_names(removed):
                return True
        added_ex = sum(1 for ln in added if EXPORT_RE.search(ln))
        removed_ex = sum(1 for ln in removed if EXPORT_RE.search(ln))
        if added_ex > removed_ex:
            return True
    return False


def net_line_delta(proposal: dict[str, Any], worktree: Path | None = None) -> int:
    if _is_candidate(proposal):
        new_n = len((proposal.get("source") or "").splitlines())
        old_n = 0
        if worktree is not None:
            target = worktree / proposal["path"]
            if target.exists():
                old_n = len(target.read_text().splitlines())
        return new_n - old_n
    delta = 0
    for edit in proposal.get("edits", []):
        diff = edit.get("unified_diff") or ""
        for ln in diff.splitlines():
            if ln.startswith("+") and not ln.startswith("+++"):
                delta += 1
            elif ln.startswith("-") and not ln.startswith("---"):
                delta -= 1
    return delta
