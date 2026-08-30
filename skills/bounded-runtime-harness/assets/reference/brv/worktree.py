from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
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
    """Apply a unified diff hunk by hunk.

    Each hunk is matched independently so replacements on distant lines
    are not flattened into one contiguous minus-sequence.
    """
    if not diff.strip():
        return existing
    old = existing.splitlines()
    for hunk in _hunks(diff):
        old = _apply_hunk(old, hunk)
    if existing.endswith("\n") or existing == "":
        return "\n".join(old) + ("\n" if old else "")
    return "\n".join(old)


# ---------------------------------------------------------------------------
# Worktree backends
# ---------------------------------------------------------------------------


class WorktreeBackend(ABC):
    """Acquires and releases an isolated working directory for one proposal."""

    @abstractmethod
    def acquire(self, authoritative: Path) -> Path:
        """Return the path to an isolated working directory."""

    @abstractmethod
    def release(self) -> None:
        """Release the working directory. Idempotent."""


class TreehouseBackend(WorktreeBackend):
    """Leased git worktree via the ``treehouse`` CLI.

    Selected when ``treehouse`` is on PATH and *authoritative* lives
    inside a git (or jj) repository.
    """

    def __init__(self) -> None:
        self._lease_id: str | None = None
        self._path: Path | None = None

    def acquire(self, authoritative: Path) -> Path:
        result = subprocess.run(
            ["treehouse", "get", "--lease", "--json", "--no-fetch"],
            cwd=authoritative,
            capture_output=True,
            text=True,
            check=True,
        )
        info = json.loads(result.stdout)
        self._lease_id = info["lease_id"]
        self._path = Path(info["path"])
        return self._path

    def release(self) -> None:
        if self._path is None or self._lease_id is None:
            return
        subprocess.run(
            [
                "treehouse", "return", "--force",
                "--if-lease-id", self._lease_id,
                str(self._path),
            ],
            capture_output=True,
        )
        self._lease_id = None
        self._path = None


class GitWorktreeBackend(WorktreeBackend):
    """Detached-HEAD linked worktree via ``git worktree add``.

    Selected when the authoritative tree is a git repo with at least
    one commit but ``treehouse`` is not available.
    """

    def __init__(self) -> None:
        self._worktree: Path | None = None
        self._parent: Path | None = None
        self._authoritative: Path | None = None

    def acquire(self, authoritative: Path) -> Path:
        self._authoritative = authoritative
        self._parent = Path(tempfile.mkdtemp(prefix="brv-gwt-"))
        self._worktree = self._parent / "tree"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(self._worktree)],
            cwd=authoritative,
            capture_output=True,
            check=True,
        )
        return self._worktree

    def release(self) -> None:
        if self._worktree is None:
            return
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(self._worktree)],
            cwd=self._authoritative,
            capture_output=True,
        )
        if self._parent and self._parent.exists():
            shutil.rmtree(self._parent, ignore_errors=True)
        self._worktree = None
        self._parent = None
        self._authoritative = None


class TempCopyBackend(WorktreeBackend):
    """Plain filesystem copy into a temp directory.

    Fallback when the authoritative tree is not under version control.
    """

    def __init__(self) -> None:
        self._temp: Path | None = None

    def acquire(self, authoritative: Path) -> Path:
        self._temp = Path(tempfile.mkdtemp(prefix="brv-"))
        if authoritative.exists():
            shutil.copytree(authoritative, self._temp, dirs_exist_ok=True)
        return self._temp

    def release(self) -> None:
        if self._temp and self._temp.exists():
            shutil.rmtree(self._temp, ignore_errors=True)
        self._temp = None


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _is_git_repo(path: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path, capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _git_has_head(path: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=path, capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _treehouse_available() -> bool:
    return shutil.which("treehouse") is not None


def select_backend(authoritative: Path) -> WorktreeBackend:
    is_git = _is_git_repo(authoritative)
    is_jj = authoritative.exists() and (authoritative / ".jj").is_dir()
    if (is_git or is_jj) and _treehouse_available():
        return TreehouseBackend()
    if is_git and _git_has_head(authoritative):
        return GitWorktreeBackend()
    return TempCopyBackend()


# ---------------------------------------------------------------------------
# Transaction (controller contract unchanged)
# ---------------------------------------------------------------------------


class WorktreeTransaction:
    """Copy-on-write sandbox. Authoritative tree is untouched until commit.

    The decisive invariant: bytes written on commit are the bytes that
    were hashed and gated, not a later mutation of the proposal.
    """

    def __init__(
        self,
        authoritative: Path,
        backend: WorktreeBackend | None = None,
    ):
        self.authoritative = Path(authoritative)
        self.temp: Path | None = None
        self.bound_sha256: str | None = None
        self.bound_edits: list[dict[str, Any]] | None = None
        self._backend: WorktreeBackend | None = backend

    def __enter__(self) -> "WorktreeTransaction":
        if self._backend is None:
            self._backend = select_backend(self.authoritative)
        self.temp = self._backend.acquire(self.authoritative)
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
        if self._backend is not None:
            self._backend.release()
            self._backend = None
        self.temp = None
        self.bound_sha256 = None
        self.bound_edits = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
