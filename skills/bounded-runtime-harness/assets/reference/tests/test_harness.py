from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from brv.controller import Controller
from brv.envelope import content_sha256, hash_proposal
from brv.evidence import make_record
from brv.gates import authorize_tool
from brv.worktree import (
    TempCopyBackend,
    WorktreeBackend,
    WorktreeTransaction,
    apply_unified_diff,
    select_backend,
)


def contract(**overrides):
    base = {
        "contract_id": "review-repair-v1",
        "task_type": "review-repair",
        "allowed_paths": ["src"],
        "allowed_tools": ["read_file", "write_file", "run_oracle"],
        "allowed_commands": ["pytest -q"],
        "oracles": [{"id": "unit", "cmd": "pytest -q", "expect_exit": 0}],
        "budget": {"max_files": 1, "max_turns": 8, "max_retries": 2, "timeout_s": 30},
        "predicates": {
            "forbid_new_files": True,
            "forbid_version_bump": True,
            "forbid_public_export_growth": True,
            "net_non_positive_lines": True,
            "one_file_scope": True,
        },
    }
    base.update(overrides)
    return base


def proposal(**overrides):
    base = {
        "schema_version": "1.0",
        "contract_id": "review-repair-v1",
        "intent": "edit",
        "edits": [
            {
                "path": "src/mod.py",
                "action": "modify",
                "unified_diff": "--- a/src/mod.py\n+++ b/src/mod.py\n-x = 1\n+x = 2\n",
            }
        ],
        "tool_calls": [],
    }
    base.update(overrides)
    return base


class HarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="brv-test-"))
        (self.tmp / "src").mkdir()
        (self.tmp / "src" / "mod.py").write_text("x = 1\n")
        self.evidence = self.tmp / "evidence"

    def ctl(self, **c) -> Controller:
        return Controller(self.tmp, contract(**c), self.evidence)

    def test_accept_writes_bound_bytes(self):
        p = proposal()
        ctl = self.ctl()
        rec = ctl.ingest_proposal(p)
        self.assertEqual(rec["decision"], "ACCEPT")
        self.assertTrue(rec["write_authorized"])
        self.assertEqual(rec["proposal_sha256"], hash_proposal(p))
        self.assertIn("x = 2", (self.tmp / "src" / "mod.py").read_text())

    def test_out_of_scope_does_not_touch_authoritative(self):
        p = proposal(
            edits=[
                {
                    "path": "secrets/prod.env",
                    "action": "modify",
                    "unified_diff": "+PASSWORD=1\n",
                }
            ]
        )
        before = (self.tmp / "src" / "mod.py").read_text()
        rec = self.ctl().ingest_proposal(p)
        self.assertEqual(rec["decision"], "REJECT")
        self.assertFalse(rec["write_authorized"])
        self.assertEqual((self.tmp / "src" / "mod.py").read_text(), before)
        self.assertFalse((self.tmp / "secrets" / "prod.env").exists())

    def test_absolute_path_is_rejected(self):
        rec = self.ctl().ingest_proposal(
            proposal(
                edits=[
                    {
                        "path": "/src/mod.py",
                        "action": "modify",
                        "unified_diff": "-x = 1\n+x = 9\n",
                    }
                ]
            )
        )
        self.assertNotEqual(rec["decision"], "ACCEPT")
        self.assertEqual((self.tmp / "src" / "mod.py").read_text(), "x = 1\n")

    def test_parent_relative_path_is_rejected(self):
        rec = self.ctl().ingest_proposal(
            proposal(
                edits=[
                    {
                        "path": "../src/mod.py",
                        "action": "modify",
                        "unified_diff": "-x = 1\n+x = 9\n",
                    }
                ]
            )
        )
        self.assertNotEqual(rec["decision"], "ACCEPT")
        self.assertEqual((self.tmp / "src" / "mod.py").read_text(), "x = 1\n")

    def test_new_file_blocked_by_review_repair(self):
        p = proposal(
            edits=[
                {
                    "path": "src/new.py",
                    "action": "create",
                    "unified_diff": "+print(1)\n",
                }
            ]
        )
        rec = self.ctl().ingest_proposal(p)
        self.assertEqual(rec["decision"], "REJECT")
        self.assertIn("INV-1", " ".join(rec["reasons"]))
        self.assertFalse((self.tmp / "src" / "new.py").exists())

    def test_tool_write_without_accept_is_denied(self):
        ok, reason = authorize_tool(
            {"name": "write_file", "args": {"path": "src/mod.py"}},
            contract(),
            {"write_authorized": False, "turns": 0, "files_touched": 0},
        )
        self.assertFalse(ok)
        self.assertIn("not authorized", reason)

    def test_command_suffix_is_not_allow_listed(self):
        ok, reason = authorize_tool(
            {"name": "run_command", "args": {"cmd": "pytest -q; id"}},
            contract(allowed_tools=["run_command"], allowed_commands=["pytest -q"]),
            {"write_authorized": False, "turns": 0, "files_touched": 0},
        )
        self.assertFalse(ok)
        self.assertIn("not allow-listed", reason)

    def test_commit_refuses_mismatched_hash(self):
        with WorktreeTransaction(self.tmp) as txn:
            txn.bind("a" * 64, [])
            with self.assertRaises(RuntimeError):
                txn.commit("b" * 64)

    def test_invalid_envelope_rejected(self):
        rec = self.ctl().ingest_proposal("not-json")
        self.assertEqual(rec["decision"], "REJECT")
        self.assertEqual(rec["gates"]["parse_compile"], "FAIL")

    def test_disallowed_tool_enum_fails_parse(self):
        rec = self.ctl().ingest_proposal(
            proposal(tool_calls=[{"name": "sudo", "args": {}}])
        )
        self.assertEqual(rec["gates"]["parse_compile"], "FAIL")
        self.assertNotEqual(rec["decision"], "ACCEPT")

    def test_invalid_python_edit_does_not_write(self):
        rec = self.ctl().ingest_proposal(
            proposal(
                edits=[
                    {
                        "path": "src/mod.py",
                        "action": "modify",
                        "unified_diff": "-x = 1\n+def broken(\n",
                    }
                ]
            )
        )
        self.assertEqual(rec["decision"], "REJECT")
        self.assertEqual(rec["gates"]["parse_compile"], "FAIL")
        self.assertEqual((self.tmp / "src" / "mod.py").read_text(), "x = 1\n")

    def test_disallowed_tool_call_does_not_commit(self):
        rec = self.ctl().ingest_proposal(
            proposal(tool_calls=[{"name": "run_command", "args": {"cmd": "pytest -q"}}])
        )
        self.assertEqual(rec["decision"], "HALT")
        self.assertFalse(rec["write_authorized"])
        self.assertEqual((self.tmp / "src" / "mod.py").read_text(), "x = 1\n")

    def test_failed_oracle_does_not_commit(self):
        ctl = Controller(
            self.tmp,
            contract(),
            self.evidence,
            oracle_runner=lambda _c, _p: False,
        )
        rec = ctl.ingest_proposal(proposal())
        self.assertEqual(rec["decision"], "HALT")
        self.assertFalse(rec["write_authorized"])
        self.assertEqual((self.tmp / "src" / "mod.py").read_text(), "x = 1\n")
        payload = json.loads((self.evidence / "run-001-1.json").read_text())
        self.assertEqual(payload["decision"], "HALT")
        self.assertFalse(payload["write_authorized"])

    def test_accepted_write_file_tool_is_authorized(self):
        rec = self.ctl().ingest_proposal(
            proposal(tool_calls=[{"name": "write_file", "args": {"path": "src/mod.py"}}])
        )
        self.assertEqual(rec["decision"], "ACCEPT")
        self.assertTrue(rec["write_authorized"])
        self.assertIn("x = 2", (self.tmp / "src" / "mod.py").read_text())

    def test_unified_diff_replaces_in_place(self):
        existing = "def a():\n    x = 1\n\ndef b():\n    return 2\n"
        diff = "--- a/src/mod.py\n+++ b/src/mod.py\n-    x = 1\n+    x = 2\n"
        out = apply_unified_diff(existing, diff)
        self.assertEqual(out, "def a():\n    x = 2\n\ndef b():\n    return 2\n")

    def test_multi_hunk_diff_applies(self):
        existing = "a = 1\nb = 2\nc = 3\n"
        diff = (
            "--- a/src/mod.py\n+++ b/src/mod.py\n"
            "@@ -1,1 +1,1 @@\n-a = 1\n+a = 8\n"
            "@@ -3,1 +3,1 @@\n-c = 3\n+c = 9\n"
        )
        out = apply_unified_diff(existing, diff)
        self.assertEqual(out, "a = 8\nb = 2\nc = 9\n")

    def test_evidence_written(self):
        self.ctl().ingest_proposal(proposal())
        files = list(self.evidence.glob("*.json"))
        self.assertTrue(files)
        payload = json.loads(files[0].read_text())
        self.assertIn("proposal_sha256", payload)
        self.assertIn("gates", payload)

    def test_duplicate_evidence_write_is_rejected(self):
        rec = make_record(
            "run-001",
            1,
            "a" * 64,
            "review-repair-v1",
            {
                "parse_compile": "PASS",
                "scope": "PASS",
                "secrets": "PASS",
                "injection": "PASS",
                "contract_preview": "PASS",
                "retry_policy": "PASS",
            },
            "ACCEPT",
            [],
        )
        rec.write(self.evidence)
        original = (self.evidence / "run-001-1.json").read_text()
        with self.assertRaises(FileExistsError):
            rec.write(self.evidence)
        self.assertEqual((self.evidence / "run-001-1.json").read_text(), original)

    def _candidate(self, source: str, path: str = "src/mod.py", **extra):
        body = {
            "schema_version": "1.1",
            "kind": "candidate",
            "contract_id": "review-repair-v1",
            "language": "python",
            "path": path,
            "source": source,
        }
        body.update(extra)
        return body

    def test_candidate_invalid_python_does_not_write(self):
        before = (self.tmp / "src" / "mod.py").read_text()
        rec = self.ctl().ingest_proposal(self._candidate("def broken(\n"))
        self.assertEqual(rec["decision"], "REJECT")
        self.assertEqual(rec["gates"]["parse_compile"], "FAIL")
        self.assertEqual((self.tmp / "src" / "mod.py").read_text(), before)

    def test_candidate_accept_writes_exact_source_bytes(self):
        source = "x = 2\n"
        p = self._candidate(source)
        rec = self.ctl().ingest_proposal(p)
        self.assertEqual(rec["decision"], "ACCEPT")
        written = (self.tmp / "src" / "mod.py").read_bytes()
        self.assertEqual(written, source.encode("utf-8"))
        self.assertEqual(rec["content_sha256"], content_sha256(p))
        self.assertEqual(rec["proposal_sha256"], hash_proposal(p))

    def test_candidate_new_path_rejected_under_review_repair(self):
        rec = self.ctl().ingest_proposal(self._candidate("x = 1\n", path="src/other.py"))
        self.assertEqual(rec["decision"], "REJECT")
        self.assertFalse((self.tmp / "src" / "other.py").exists())

    def test_candidate_schema_valid_json_invalid_python(self):
        rec = self.ctl().ingest_proposal(self._candidate("not python at all !!!"))
        self.assertEqual(rec["gates"]["parse_compile"], "FAIL")
        self.assertFalse(rec["write_authorized"])


# ---------------------------------------------------------------------------
# Backend tests
# ---------------------------------------------------------------------------

class TempCopyBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="brv-test-tcp-"))
        (self.tmp / "src").mkdir()
        (self.tmp / "src" / "f.txt").write_text("hello\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_acquire_copies_tree(self):
        backend = TempCopyBackend()
        wt = backend.acquire(self.tmp)
        self.assertTrue((wt / "src" / "f.txt").exists())
        self.assertEqual((wt / "src" / "f.txt").read_text(), "hello\n")
        backend.release()

    def test_release_removes_tree(self):
        backend = TempCopyBackend()
        wt = backend.acquire(self.tmp)
        backend.release()
        self.assertFalse(wt.exists())

    def test_release_is_idempotent(self):
        backend = TempCopyBackend()
        backend.acquire(self.tmp)
        backend.release()
        backend.release()

    def test_transaction_uses_temp_copy(self):
        with WorktreeTransaction(self.tmp, backend=TempCopyBackend()) as txn:
            self.assertIsNotNone(txn.temp)
            self.assertTrue((txn.temp / "src" / "f.txt").exists())


class BackendSelectionTests(unittest.TestCase):
    def test_non_vcs_selects_temp_copy(self):
        tmp = Path(tempfile.mkdtemp(prefix="brv-test-sel-"))
        try:
            backend = select_backend(tmp)
            self.assertIsInstance(backend, TempCopyBackend)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_backend_abc_cannot_instantiate(self):
        with self.assertRaises(TypeError):
            WorktreeBackend()


if __name__ == "__main__":
    unittest.main()
