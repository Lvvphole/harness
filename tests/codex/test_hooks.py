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


def review_contract(**overrides: object) -> dict[str, object]:
    predicates = {key: True for key in contract()["predicates"]}
    value = contract(task_type="review-repair", predicates=predicates)
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
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")

    def invoke(self, event: str, **fields: object) -> subprocess.CompletedProcess[str]:
        payload = {
            "session_id": "session-1",
            "turn_id": "turn-1",
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

    def assert_denied(self, result: subprocess.CompletedProcess[str], text: str) -> None:
        output = self.output(result)["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn(text, output["permissionDecisionReason"])

    def test_config_uses_native_event_keyed_shape(self) -> None:
        config = json.loads(HOOKS.read_text(encoding="utf-8"))
        expected = {
            "SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest",
            "PostToolUse", "Stop", "SessionEnd",
        }
        self.assertEqual(set(config["hooks"]), expected)
        for groups in config["hooks"].values():
            handler = groups[0]["hooks"][0]
            self.assertEqual(handler["type"], "command")
            self.assertIn("$PLUGIN_ROOT/hooks/dispatch.py", handler["command"])
            self.assertIn("%PLUGIN_ROOT%", handler["commandWindows"])

    def test_missing_contract_denies_mutation(self) -> None:
        self.assert_denied(
            self.invoke(
                "PreToolUse", tool_name="Bash", tool_use_id="missing-contract",
                tool_input={"command": "python3 -m unittest"},
            ),
            "active contract",
        )

    def test_incomplete_contract_never_authorizes_a_tool(self) -> None:
        cases = [
            {key: value for key, value in contract().items() if key != "task_type"},
            {key: value for key, value in contract().items() if key != "predicates"},
            contract(allowed_tools=["write_file", "unbounded_shell"]),
            contract(unrecognized=True),
        ]
        for index, value in enumerate(cases):
            with self.subTest(index=index):
                self.write_contract(value)
                self.assert_denied(
                    self.invoke(
                        "PreToolUse", tool_name="apply_patch", tool_use_id=f"schema-{index}",
                        tool_input={"command": "*** Begin Patch\n*** Add File: src/a.py\n+x = 1\n*** End Patch"},
                    ),
                    "active contract",
                )

    def test_review_repair_predicate_blocks_prohibited_work(self) -> None:
        self.write_contract(review_contract())
        self.assert_denied(
            self.invoke(
                "PreToolUse", tool_name="apply_patch", tool_use_id="repair-new-file",
                tool_input={"command": "*** Begin Patch\n*** Add File: src/new.py\n+x = 1\n*** End Patch"},
            ),
            "forbid_new_files",
        )

    def test_review_repair_requires_every_predicate_true(self) -> None:
        predicates = {key: False for key in contract()["predicates"]}
        self.write_contract(contract(task_type="review-repair", predicates=predicates))
        self.assert_denied(
            self.invoke(
                "PreToolUse", tool_name="apply_patch", tool_use_id="disabled-predicates",
                tool_input={"command": "*** Begin Patch\n*** Add File: src/new.py\n+x = 1\n*** End Patch"},
            ),
            "active contract",
        )

    def test_python_review_repair_cannot_grow_public_exports(self) -> None:
        source = self.work / "src" / "value.py"
        source.parent.mkdir()
        source.write_text("def _private():\n    pass\n", encoding="utf-8")
        self.write_contract(review_contract())
        self.assert_denied(
            self.invoke(
                "PreToolUse", tool_name="apply_patch", tool_use_id="python-export",
                tool_input={"command": "*** Begin Patch\n*** Update File: src/value.py\n@@\n-def _private():\n+def public():\n     pass\n*** End Patch"},
            ),
            "forbid_public_export_growth",
        )

    def test_read_tools_cannot_escape_allowed_paths(self) -> None:
        self.write_contract(contract())
        for name, tool_input in {
            "Read": {"file_path": "/etc/passwd"},
            "read_file": {"path": "README.md"},
            "Grep": {"path": "tests", "pattern": "secret"},
            "Glob": {"path": "..", "pattern": "**/*"},
        }.items():
            with self.subTest(name=name):
                self.assert_denied(
                    self.invoke(
                        "PreToolUse", tool_name=name, tool_use_id=f"read-{name}",
                        tool_input=tool_input,
                    ),
                    "out of scope",
                )

    def test_read_symlink_cannot_escape_allowed_paths(self) -> None:
        source = self.work / "src"
        source.mkdir()
        try:
            (source / "out").symlink_to("/etc/passwd")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        self.write_contract(contract())
        self.assert_denied(
            self.invoke(
                "PreToolUse", tool_name="Read", tool_use_id="symlink-read",
                tool_input={"file_path": "src/out"},
            ),
            "out of scope",
        )

    def test_result_uses_the_accepted_proposal_contract(self) -> None:
        first = contract(contract_id="contract-1")
        self.write_contract(first)
        tool_input = {"command": "python3 -m unittest"}
        self.assertEqual(
            self.output(self.invoke(
                "PreToolUse", tool_name="Bash", tool_use_id="bound-result",
                tool_input=tool_input,
            )),
            {},
        )
        self.write_contract(contract(contract_id="contract-2"))
        self.assertEqual(
            self.output(self.invoke(
                "PostToolUse", tool_name="Bash", tool_use_id="bound-result",
                tool_input=tool_input, tool_response={"exit_code": 0},
            )),
            {},
        )
        record = json.loads(
            (self.data / "runs" / "session-1" / "bound-result.result.json").read_text()
        )
        self.assertEqual(record["contract_id"], "contract-1")
        self.assertEqual(record["provenance_verdict"], "PASS")

    def test_result_input_mismatch_blocks_and_records_failure(self) -> None:
        self.write_contract(contract())
        self.assertEqual(
            self.output(self.invoke(
                "PreToolUse", tool_name="Bash", tool_use_id="mismatched-result",
                tool_input={"command": "python3 -m unittest"},
            )),
            {},
        )
        output = self.output(self.invoke(
            "PostToolUse", tool_name="Bash", tool_use_id="mismatched-result",
            tool_input={"command": "different command"}, tool_response={"exit_code": 0},
        ))
        self.assertEqual(output["decision"], "block")
        record = json.loads(
            (self.data / "runs" / "session-1" / "mismatched-result.result.json").read_text()
        )
        self.assertEqual(record["provenance_verdict"], "FAIL")

    def test_result_without_proposal_blocks_and_records_failure(self) -> None:
        self.write_contract(contract())
        output = self.output(self.invoke(
            "PostToolUse", tool_name="Bash", tool_use_id="missing-proposal",
            tool_input={"command": "python3 -m unittest"}, tool_response={"exit_code": 0},
        ))
        self.assertEqual(output["decision"], "block")
        record = json.loads(
            (self.data / "runs" / "session-1" / "missing-proposal.result.json").read_text()
        )
        self.assertEqual(record["provenance_verdict"], "FAIL")
        self.assertIsNone(record["proposal_sha256"])


if __name__ == "__main__":
    unittest.main()
