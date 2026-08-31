#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DISPATCH = ROOT / "hooks" / "dispatch.py"
HOOKS = ROOT / "hooks" / "hooks.json"


def contract(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "contract_id": "contract-1",
        "task_type": "feature-development",
        "allowed_paths": ["src/"],
        "allowed_tools": ["read_file", "write_file", "run_command", "run_oracle"],
        "allowed_commands": ["python3 -m unittest"],
        "oracles": [],
        "budget": {"max_files": 4, "max_turns": 8, "max_retries": 2, "timeout_s": 30},
        "predicates": {
            "forbid_new_files": False,
            "forbid_version_bump": False,
            "forbid_public_export_growth": False,
            "net_non_positive_lines": False,
            "one_file_scope": False,
        },
    }
    value.update(overrides)
    return value


class HookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name) / "repo"
        self.data = Path(self.temp.name) / "data"
        self.work.mkdir()

    def write_contract(self, value: dict[str, object]) -> None:
        target = self.work / ".harness" / "runtime" / "active-contract.json"
        target.parent.mkdir(parents=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def invoke(self, event: str, **fields: object) -> subprocess.CompletedProcess[str]:
        payload = {
            "session_id": "session-1",
            "turn_id": "turn-1",
            "transcript_path": None,
            "cwd": str(self.work),
            "hook_event_name": event,
            "permission_mode": "default",
        }
        payload.update(fields)
        env = os.environ.copy()
        env.update({"PLUGIN_ROOT": str(ROOT), "PLUGIN_DATA": str(self.data)})
        return subprocess.run(
            [sys.executable, str(DISPATCH), event],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def output(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout or "{}")

    def test_config_uses_native_event_keyed_shape(self) -> None:
        config = json.loads(HOOKS.read_text(encoding="utf-8"))
        expected = {
            "SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest",
            "PostToolUse", "Stop", "SessionEnd",
        }
        self.assertEqual(set(config["hooks"]), expected)
        for groups in config["hooks"].values():
            self.assertIsInstance(groups, list)
            handler = groups[0]["hooks"][0]
            self.assertEqual(handler["type"], "command")
            self.assertIn("$PLUGIN_ROOT/hooks/dispatch.py", handler["command"])
            self.assertIn("%PLUGIN_ROOT%", handler["commandWindows"])

    def test_missing_contract_denies_mutation(self) -> None:
        result = self.invoke(
            "PreToolUse", tool_name="Bash", tool_use_id="tool-1",
            tool_input={"command": "python3 -m unittest"},
        )
        output = self.output(result)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("active contract", output["permissionDecisionReason"])

    def test_empty_command_allowlist_is_fail_closed(self) -> None:
        self.write_contract(contract(allowed_commands=[]))
        result = self.invoke(
            "PreToolUse", tool_name="Bash", tool_use_id="tool-2",
            tool_input={"command": "rm -rf build"},
        )
        output = self.output(result)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("not allow-listed", output["permissionDecisionReason"])

    def test_exact_allowlisted_command_defers_to_normal_permissions(self) -> None:
        self.write_contract(contract())
        result = self.invoke(
            "PreToolUse", tool_name="Bash", tool_use_id="tool-3",
            tool_input={"command": "python3 -m unittest"},
        )
        self.assertEqual(self.output(result), {})

    def test_out_of_scope_patch_is_denied_before_execution(self) -> None:
        self.write_contract(contract())
        result = self.invoke(
            "PreToolUse", tool_name="apply_patch", tool_use_id="tool-4",
            tool_input={"command": "*** Begin Patch\n*** Add File: README.md\n+x\n*** End Patch"},
        )
        output = self.output(result)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("out of scope", output["permissionDecisionReason"])

    def test_permitted_patch_records_exact_proposal(self) -> None:
        self.write_contract(contract())
        tool_input = {
            "command": "*** Begin Patch\n*** Add File: src/value.py\n+VALUE = 1\n*** End Patch"
        }
        result = self.invoke(
            "PreToolUse", tool_name="apply_patch", tool_use_id="tool-5",
            tool_input=tool_input,
        )
        self.assertEqual(self.output(result), {})
        path = self.data / "runs" / "session-1" / "tool-5.proposal.json"
        record = json.loads(path.read_text())
        self.assertEqual(record["information_state"], "VERIFIED")
        self.assertEqual(record["tool_input"], tool_input)
        self.assertEqual(record["contract_id"], "contract-1")
        self.assertEqual(record["decision"], "ACCEPT")

    def test_permission_request_never_self_approves(self) -> None:
        self.write_contract(contract())
        allowed = self.invoke(
            "PermissionRequest", tool_name="Bash",
            tool_input={"command": "python3 -m unittest"},
        )
        self.assertEqual(self.output(allowed), {})
        denied = self.invoke(
            "PermissionRequest", tool_name="Bash",
            tool_input={"command": "git push origin main"},
        )
        decision = self.output(denied)["hookSpecificOutput"]["decision"]
        self.assertEqual(decision["behavior"], "deny")

    def test_post_tool_use_records_observation_without_accepting_it(self) -> None:
        self.write_contract(contract())
        result = self.invoke(
            "PostToolUse", tool_name="Bash", tool_use_id="tool-6",
            tool_input={"command": "python3 -m unittest"},
            tool_response={"exit_code": 0, "output": "ok"},
        )
        self.assertEqual(self.output(result), {})
        path = self.data / "runs" / "session-1" / "tool-6.result.json"
        record = json.loads(path.read_text())
        self.assertEqual(record["information_state"], "OBSERVED")
        self.assertEqual(record["tool_use_id"], "tool-6")
        self.assertEqual(record["tool_response"]["exit_code"], 0)
        self.assertNotIn("accepted", record)


if __name__ == "__main__":
    unittest.main()
