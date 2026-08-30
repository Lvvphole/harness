from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .predicates import is_unsafe_path


class PatchError(ValueError):
    pass


def sandbox_path(root: Path, rel: str) -> Path:
    if is_unsafe_path(rel):
        raise PatchError(f"unsafe path: {rel}")
    target = (root / rel).resolve()
    base = root.resolve()
    if target != base and base not in target.parents:
        raise PatchError(f"path escapes sandbox: {rel}")
    return target


def apply_unified_diff(existing: str, diff: str) -> str:
    """Apply a unified diff by matching removed lines in place.

    Rejects diffs that cannot be applied exactly. Does not append plus-lines
    to the end of the file when a replacement target exists.
    """
    if not diff.strip():
        return existing
    ops: list[str] = []
    for ln in diff.splitlines():
        if ln.startswith("+++") or ln.startswith("---") or ln.startswith("@@"):
            continue
        if ln.startswith("\\"):
            continue
        ops.append(ln)
    minus = [ln[1:] for ln in ops if ln.startswith("-")]
    plus = [ln[1:] for ln in ops if ln.startswith("+")]
    old = existing.splitlines()
    if minus:
        n = len(minus)
        found = -1
        for i in range(0, len(old) - n + 1):
            if old[i : i + n] == minus:
                found = i
                break
        if found < 0:
            raise PatchError("unified diff does not apply to existing source")
        new = old[:found] + plus + old[found + n :]
    else:
        new = old + plus
    if existing.endswith("\n") or existing == "":
        return "\n".join(new) + ("\n" if new else "")
    return "\n".join(new)


class WorktreeTransaction:
    """Copy-on-write sandbox. Authoritative tree is untouched until commit.

    The decisive invariant: bytes written on commit are the bytes that
    were hashed and gated, not a later mutation of the proposal.
    """

    def __init__(self, authoritative: Path):
        self.authoritative = Path(authoritative)
        self.temp: Path | None = None
        self.bound_sha256: str | None = None
        self.bound_edits: list[dict[str, Any]] | None = None

    def __enter__(self) -> "WorktreeTransaction":
        self.temp = Path(tempfile.mkdtemp(prefix="brv-"))
        if self.authoritative.exists():
            shutil.copytree(self.authoritative, self.temp, dirs_exist_ok=True)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.discard()

    def bind(self, proposal_sha256: str, edits: list[dict[str, Any]]) -> None:
        self.bound_sha256 = proposal_sha256
        self.bound_edits = list(edits)

    def apply_to_temp(self, edits: list[dict[str, Any]]) -> None:
        assert self.temp is not None
        for edit in edits:
            target = sandbox_path(self.temp, edit["path"])
            if edit["action"] == "delete":
                if target.exists():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if "source" in edit:
                target.write_bytes(edit["source"].encode("utf-8"))
                continue
            existing = target.read_text() if target.exists() else ""
            target.write_text(apply_unified_diff(existing, edit.get("unified_diff") or ""))

    def commit(self, proposal_sha256: str) -> list[Path]:
        if self.bound_sha256 != proposal_sha256:
            raise RuntimeError("commit hash mismatch: write refused")
        if self.temp is None or self.bound_edits is None:
            raise RuntimeError("no bound proposal")
        written: list[Path] = []
        for edit in self.bound_edits:
            src = sandbox_path(self.temp, edit["path"])
            dest = sandbox_path(self.authoritative, edit["path"])
            if edit["action"] == "delete":
                if dest.exists():
                    dest.unlink()
                written.append(dest)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())
            written.append(dest)
        return written

    def discard(self) -> None:
        if self.temp and self.temp.exists():
            shutil.rmtree(self.temp, ignore_errors=True)
        self.temp = None
        self.bound_sha256 = None
        self.bound_edits = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
