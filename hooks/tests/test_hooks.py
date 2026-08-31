from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = HOOKS_ROOT.parent
REFERENCE = REPO_ROOT / "skills" / "bounded-runtime-harness" / "assets" / "reference"
sys.path.insert(0, str(HOOKS_ROOT))
sys.path.insert(0, str(REFERENCE))

from tokens import mint_token, validate_token


class HooksJsonTests(unittest.TestCase):
    def test_hooks_json_parses(self):
        path = HOOKS_ROOT / "hooks.json"
        data = json.loads(path.read_text())
        self.assertIn("hooks", data)
        self.assertIsInstance(data["hooks"], list)

    def test_hooks_json_maps_all_seven_events(self):
        path = HOOKS_ROOT / "hooks.json"
        data = json.loads(path.read_text())
        events = {h["event"] for h in data["hooks"]}
        expected = {
            "SessionStart",
            "UserPromptSubmit",
            "PreToolUse",
            "PermissionRequest",
            "PostToolUse",
            "Stop",
            "SessionEnd",
        }
        self.assertEqual(events, expected)

    def test_hooks_json_commands_target_dispatch(self):
        path = HOOKS_ROOT / "hooks.json"
        data = json.loads(path.read_text())
        for hook in data["hooks"]:
            self.assertIn("dispatch.py", hook["command"])
            self.assertIn(hook["event"], hook["command"])


class TokenTests(unittest.TestCase):
    def setUp(self):
        self.session_id = "session-001"
        self.contract_id = "review-repair-v1"
        self.proposal_sha = "a" * 64
        self.tools = ["read_file", "write_file"]
        self.paths = ["src"]
        self.turn = 1

    def test_mint_deterministic(self):
        t1 = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        t2 = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        self.assertEqual(t1, t2)

    def test_mint_changes_with_session(self):
        t1 = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        t2 = mint_token(
            "other-session", self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        self.assertNotEqual(t1, t2)

    def test_mint_changes_with_turn(self):
        t1 = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, 1,
        )
        t2 = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, 2,
        )
        self.assertNotEqual(t1, t2)

    def test_validate_accepts_correct_token(self):
        token = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        self.assertTrue(validate_token(
            token, self.session_id, self.contract_id, self.proposal_sha,
            "write_file", "src/mod.py", self.turn,
            self.tools, self.paths,
        ))

    def test_validate_rejects_wrong_session(self):
        token = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        self.assertFalse(validate_token(
            token, "wrong-session", self.contract_id, self.proposal_sha,
            "write_file", "src/mod.py", self.turn,
            self.tools, self.paths,
        ))

    def test_validate_rejects_expired_turn(self):
        token = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, 1,
        )
        self.assertFalse(validate_token(
            token, self.session_id, self.contract_id, self.proposal_sha,
            "write_file", "src/mod.py", 2,
            self.tools, self.paths,
        ))

    def test_validate_rejects_tampered_token(self):
        token = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        tampered = "0" * len(token)
        self.assertFalse(validate_token(
            tampered, self.session_id, self.contract_id, self.proposal_sha,
            "write_file", "src/mod.py", self.turn,
            self.tools, self.paths,
        ))

    def test_validate_rejects_unpermitted_tool(self):
        token = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        self.assertFalse(validate_token(
            token, self.session_id, self.contract_id, self.proposal_sha,
            "run_command", "src/mod.py", self.turn,
            self.tools, self.paths,
        ))

    def test_validate_rejects_out_of_scope_path(self):
        token = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        self.assertFalse(validate_token(
            token, self.session_id, self.contract_id, self.proposal_sha,
            "write_file", "/etc/passwd", self.turn,
            self.tools, self.paths,
        ))

    def test_validate_allows_none_path_for_non_file_tool(self):
        token = mint_token(
            self.session_id, self.contract_id, self.proposal_sha,
            self.tools, self.paths, self.turn,
        )
        self.assertTrue(validate_token(
            token, self.session_id, self.contract_id, self.proposal_sha,
            "read_file", None, self.turn,
            self.tools, self.paths,
        ))


class DispatchIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hooks-test-"))
        self.state_file = self.tmp / "codex-session-state.json"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _save_state(self, state):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2, sort_keys=True))

    def _load_state(self):
        return json.loads(self.state_file.read_text())

    def _make_session_state(self, **overrides):
        base = {
            "session_id": "test-session",
            "contract": {
                "contract_id": "review-repair-v1",
                "task_type": "codex-session",
                "allowed_paths": ["src"],
                "allowed_tools": ["read_file", "write_file", "run_command"],
                "allowed_commands": ["pytest -q"],
                "oracles": [],
                "budget": {"max_files": 16, "max_turns": 20, "max_retries": 2, "timeout_s": 120},
                "predicates": {},
            },
            "turn": 0,
            "write_authorized": False,
            "files_touched": 0,
            "proposal_sha": None,
            "active_token": None,
            "permitted_tools": ["read_file", "write_file", "run_command"],
            "permitted_paths": ["src"],
        }
        base.update(overrides)
        return base

    def test_session_start_creates_state(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        dispatch._state_path = lambda: self.state_file
        original_stdout = sys.stdout
        try:
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_session_start({"session_id": "test-001"})
            sys.stdout = original_stdout
            state = json.loads(self.state_file.read_text())
            self.assertEqual(state["session_id"], "test-001")
            self.assertEqual(state["turn"], 0)
            self.assertFalse(state["write_authorized"])
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path

    def test_user_prompt_increments_turn(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        dispatch._state_path = lambda: self.state_file
        original_stdout = sys.stdout
        try:
            self._save_state(self._make_session_state(turn=2))
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_user_prompt_submit({})
            sys.stdout = original_stdout
            state = self._load_state()
            self.assertEqual(state["turn"], 3)
            self.assertFalse(state["write_authorized"])
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path

    def test_pre_tool_use_denies_write_without_token(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        dispatch._state_path = lambda: self.state_file
        original_stdout = sys.stdout
        try:
            self._save_state(self._make_session_state(
                turn=1, write_authorized=True, active_token=None,
            ))
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_pre_tool_use({
                "tool": {"name": "write_file", "args": {"path": "src/mod.py"}},
            })
            sys.stdout = original_stdout
            output = json.loads(capture.getvalue().strip())
            self.assertEqual(output["decision"], "deny")
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path

    def test_pre_tool_use_allows_write_with_valid_token(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        dispatch._state_path = lambda: self.state_file
        original_stdout = sys.stdout
        try:
            proposal_sha = "a" * 64
            tools = ["read_file", "write_file", "run_command"]
            paths = ["src"]
            token = mint_token("test-session", "review-repair-v1", proposal_sha, tools, paths, 1)
            self._save_state(self._make_session_state(
                turn=1,
                write_authorized=True,
                proposal_sha=proposal_sha,
                active_token=token,
            ))
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_pre_tool_use({
                "tool": {"name": "write_file", "args": {"path": "src/mod.py"}},
            })
            sys.stdout = original_stdout
            output = json.loads(capture.getvalue().strip())
            self.assertEqual(output["decision"], "approve")
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path

    def test_pre_tool_use_allows_read_without_token(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        dispatch._state_path = lambda: self.state_file
        original_stdout = sys.stdout
        try:
            self._save_state(self._make_session_state(turn=1))
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_pre_tool_use({
                "tool": {"name": "read_file", "args": {"path": "src/mod.py"}},
            })
            sys.stdout = original_stdout
            output = json.loads(capture.getvalue().strip())
            self.assertEqual(output["decision"], "approve")
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path

    def test_post_tool_use_increments_files_touched(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        dispatch._state_path = lambda: self.state_file
        original_stdout = sys.stdout
        try:
            self._save_state(self._make_session_state(turn=1, files_touched=0))
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_post_tool_use({
                "tool": {"name": "write_file", "args": {"path": "src/mod.py"}},
            })
            sys.stdout = original_stdout
            state = self._load_state()
            self.assertEqual(state["files_touched"], 1)
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path

    def test_stop_writes_evidence(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        original_evidence_path = dispatch._evidence_path
        dispatch._state_path = lambda: self.state_file
        evidence_dir = self.tmp / "evidence"
        dispatch._evidence_path = lambda: evidence_dir
        original_stdout = sys.stdout
        try:
            self._save_state(self._make_session_state(
                session_id="test-stop", turn=5, files_touched=3,
            ))
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_stop({"reason": "user requested"})
            sys.stdout = original_stdout
            summary_path = evidence_dir / "codex-stop-summary.json"
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text())
            self.assertEqual(summary["session_id"], "test-stop")
            self.assertEqual(summary["turn"], 5)
            self.assertEqual(summary["reason"], "user requested")
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path
            dispatch._evidence_path = original_evidence_path

    def test_session_end_seals_evidence(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        original_evidence_path = dispatch._evidence_path
        dispatch._state_path = lambda: self.state_file
        evidence_dir = self.tmp / "evidence"
        dispatch._evidence_path = lambda: evidence_dir
        original_stdout = sys.stdout
        try:
            self._save_state(self._make_session_state(
                session_id="test-seal", turn=8, files_touched=2,
            ))
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_session_end({})
            sys.stdout = original_stdout
            seal_path = evidence_dir / "codex-session-seal.json"
            self.assertTrue(seal_path.exists())
            seal = json.loads(seal_path.read_text())
            self.assertTrue(seal["sealed"])
            self.assertEqual(seal["session_id"], "test-seal")
            self.assertFalse(self.state_file.exists())
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path
            dispatch._evidence_path = original_evidence_path

    def test_permission_request_denies_disallowed_tool(self):
        import dispatch
        import io
        original_state_path = dispatch._state_path
        dispatch._state_path = lambda: self.state_file
        original_stdout = sys.stdout
        try:
            self._save_state(self._make_session_state(turn=1))
            capture = io.StringIO()
            sys.stdout = capture
            dispatch.handle_permission_request({
                "tool": {"name": "sudo", "args": {}},
            })
            sys.stdout = original_stdout
            output = json.loads(capture.getvalue().strip())
            self.assertEqual(output["decision"], "deny")
        finally:
            sys.stdout = original_stdout
            dispatch._state_path = original_state_path


if __name__ == "__main__":
    unittest.main()
