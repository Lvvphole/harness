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
    base = Path(root).resolve()
    current = base
    parts = [part for part in rel.replace("\\", "/").split("/") if part not in ("", ".")]
    for part in parts:
        nxt = current / part
        if nxt.is_symlink():
            raise PatchError(f"symlink refused: {rel}")
        current = nxt
    target = current.resolve()
    if target != base and base not in target.parents:
        raise PatchError(f"path escapes sandbox: {rel}")
    return target


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.is_symlink():
            continue
        target = dst / item.name
        if item.is_dir():
            _copy_tree(item, target)
        elif item.is_file():
            shutil.copy2(item, target)


def _hunks(diff: str) -> list[list[str]]:
    hunks: list[list[str]] = []
    current: list[str] = []
    for ln in diff.splitlines():
        if ln.startswith("+++") or ln.startswith("---") or ln.startswith("\\"):
            continue
        if ln.startswith("@@"):
            if current:
                hunks.append(current)
                current = []
            continue
        current.append(ln)
    if current:
        hunks.append(current)
    return hunks


def _apply_hunk(old: list[str], ops: list[str]) -> list[str]:
    old_side: list[str] = []
    new_side: list[str] = []
    for ln in ops:
        if ln.startswith("+") and not ln.startswith("+++"):
            new_side.append(ln[1:])
        elif ln.startswith("-") and not ln.startswith("---"):
            old_side.append(ln[1:])
        else:
            text = ln[1:] if ln.startswith(" ") else ln
            old_side.append(text)
            new_side.append(text)
    if not old_side:
        return old + new_side
    n = len(old_side)
    found = -1
    for i in range(0, len(old) - n + 1):
        if old[i : i + n] == old_side:
            found = i
            break
    if found < 0:
        raise PatchError("unified diff does not apply to existing source")
    return old[:found] + new_side + old[found + n :]


def apply_unified_diff(existing: str, diff: str) -> str:
    if not diff.strip():
        return existing
    old = existing.splitlines()
    for hunk in _hunks(diff):
        old = _apply_hunk(old, hunk)
    if existing.endswith("\n") or existing == "":
        return "\n".join(old) + ("\n" if old else "")
    return "\n".join(old)


class WorktreeTransaction:
    def __init__(self, authoritative: Path):
        self.authoritative = Path(authoritative)
        self.temp: Path | None = None
        self.bound_sha256: str | None = None
        self.bound_edits: list[dict[str, Any]] | None = None

    def __enter__(self) -> "WorktreeTransaction":
        self.temp = Path(tempfile.mkdtemp(prefix="brv-"))
        if self.authoritative.exists():
            _copy_tree(self.authoritative, self.temp)
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
                if target.exists() and not target.is_symlink():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if "source" in edit:
                target.write_bytes(edit["source"].encode("utf-8"))
                continue
            existing = ""
            if target.exists() and target.is_file():
                try:
                    existing = target.read_text()
                except (OSError, UnicodeDecodeError) as exc:
                    raise PatchError(f"cannot read {edit['path']}: {exc}") from exc
            target.write_text(apply_unified_diff(existing, edit.get("unified_diff") or ""))

    def commit(self, proposal_sha256: str) -> list[Path]:
        if self.bound_sha256 != proposal_sha256:
            raise RuntimeError("commit hash mismatch: write refused")
        if self.temp is None or self.bound_edits is None:
            raise RuntimeError("no bound proposal")
        planned: list[tuple[Path, bytes | None]] = []
        for edit in self.bound_edits:
            dest = sandbox_path(self.authoritative, edit["path"])
            if edit["action"] == "delete":
                planned.append((dest, None))
                continue
            src = sandbox_path(self.temp, edit["path"])
            planned.append((dest, src.read_bytes()))
        written: list[Path] = []
        for dest, payload in planned:
            if payload is None:
                if dest.exists() and dest.is_file() and not dest.is_symlink():
                    dest.unlink()
                written.append(dest)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
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
