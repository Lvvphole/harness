from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Any


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
            target = self.temp / edit["path"]
            if edit["action"] == "delete":
                if target.exists():
                    target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if "source" in edit:
                target.write_bytes(edit["source"].encode("utf-8"))
                continue
            if edit["action"] == "create" or not target.exists():
                body = _diff_to_body(edit.get("unified_diff") or "", existing="")
                target.write_text(body)
            else:
                existing = target.read_text()
                target.write_text(_apply_simple_diff(existing, edit.get("unified_diff") or ""))

    def commit(self, proposal_sha256: str) -> list[Path]:
        if self.bound_sha256 != proposal_sha256:
            raise RuntimeError("commit hash mismatch: write refused")
        if self.temp is None or self.bound_edits is None:
            raise RuntimeError("no bound proposal")
        written: list[Path] = []
        for edit in self.bound_edits:
            src = self.temp / edit["path"]
            dest = self.authoritative / edit["path"]
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


def _diff_to_body(diff: str, existing: str) -> str:
    added = [ln[1:] for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    if added:
        return "\n".join(added) + ("\n" if added else "")
    return existing


def _apply_simple_diff(existing: str, diff: str) -> str:
    if not diff.strip():
        return existing
    if existing == "":
        return _diff_to_body(diff, existing)
    lines = existing.splitlines()
    for ln in diff.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            lines.append(ln[1:])
        elif ln.startswith("-") and not ln.startswith("---"):
            body = ln[1:]
            if body in lines:
                lines.remove(body)
    return "\n".join(lines) + ("\n" if lines else "")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
