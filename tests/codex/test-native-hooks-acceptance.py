#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REQUIRED_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "Stop",
    "SessionEnd",
)
REQUIRED_FIELDS = {
    "id",
    "pr",
    "severity",
    "family",
    "defect",
    "invariant",
    "reproducer",
    "expected",
}
EXPECTED_IDS = {
    "PR14-P1-01",
    "PR14-P1-02",
    "PR14-P1-03",
    "PR14-P1-04",
    "PR15-P1-01",
    "PR15-P1-02",
    "PR15-P1-03",
    "PR15-P2-01",
    "PR16-P1-01",
    "PR16-P1-02",
    "PR16-P1-03",
    "PR16-P1-04",
    "PR17-P1-01",
    "PR17-P1-02",
    "PR17-P2-01",
    "PR17-P2-02",
    "PR18-P1-01",
    "PR18-P1-02",
    "PR18-P1-03",
    "PR18-P1-04",
    "PR18-P2-01",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(errors, f"{path}: {exc}")
        return {}
    if not isinstance(value, dict):
        fail(errors, f"{path}: root must be an object")
        return {}
    return value


def validate_corpus(repo: Path, errors: list[str]) -> str:
    path = repo / "tests/codex/native-hooks-acceptance.json"
    raw = path.read_bytes() if path.exists() else b""
    corpus_sha256 = hashlib.sha256(raw).hexdigest()
    data = load_json(path, errors)
    cases = data.get("cases")
    if not isinstance(cases, list):
        fail(errors, "acceptance corpus cases must be an array")
        return corpus_sha256

    ids: list[str] = []
    severities: Counter[str] = Counter()
    prs: set[int] = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            fail(errors, f"case[{index}] must be an object")
            continue
        missing = REQUIRED_FIELDS - set(case)
        if missing:
            fail(errors, f"case[{index}] missing fields: {sorted(missing)}")
        case_id = case.get("id")
        if isinstance(case_id, str):
            ids.append(case_id)
        severity = case.get("severity")
        if isinstance(severity, str):
            severities[severity] += 1
        pr = case.get("pr")
        if isinstance(pr, int):
            prs.add(pr)
        for field in ("defect", "invariant", "reproducer", "expected"):
            if not isinstance(case.get(field), str) or not case[field].strip():
                fail(errors, f"{case_id or index}: {field} must be non-empty text")

    if len(cases) != 21:
        fail(errors, f"expected 21 frozen cases, got {len(cases)}")
    if set(ids) != EXPECTED_IDS or len(ids) != len(set(ids)):
        fail(errors, "frozen case identities changed or are duplicated")
    if severities != Counter({"P1": 17, "P2": 4}):
        fail(errors, f"expected severity split P1=17/P2=4, got {dict(severities)}")
    if prs != {14, 15, 16, 17, 18}:
        fail(errors, f"expected source PRs 14-18, got {sorted(prs)}")
    if data.get("expected_counts") != {"total": 21, "P1": 17, "P2": 4}:
        fail(errors, "expected_counts does not match frozen corpus identity")
    return corpus_sha256


def require_text(path: Path, needles: tuple[str, ...], errors: list[str]) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(errors, f"{path}: {exc}")
        return
    for needle in needles:
        if needle not in text:
            fail(errors, f"{path}: missing governed text {needle!r}")


def validate_governance(repo: Path, errors: list[str]) -> None:
    require_text(
        repo / "AGENTS.md",
        ("hooks/hooks.json", "hooks/list", "default-discovered hooks do not require a `hooks` field"),
        errors,
    )
    require_text(
        repo / "CONTEXT.md",
        ("`hooks/`", "Codex default hook discovery", "verify the installed artifact with native `hooks/list`"),
        errors,
    )
    require_text(repo / ".harness/inference-loop.md", ("`hooks/`", "native matcher-group shape"), errors)
    require_text(repo / ".harness/runtime-loop.md", ("test-native-hooks-acceptance.py",), errors)
    require_text(repo / ".governance/security.md", ("unconditional", "`hooks/`", "leading dots"), errors)
    require_text(repo / ".governance/testing.md", ("hooks/list", "Untrusted", "PRODUCED, NOT ACCEPTED"), errors)
    require_text(repo / ".harness/contracts/plugin-packaging.md", ("'hooks' not in m", "hooks/hooks.json", "hooks/list"), errors)
    require_text(repo / ".harness/evals.md", ("21 cases; 17 P1 and 4 P2", "Native installed hook discovery"), errors)


def validate_candidate_surface(repo: Path, errors: list[str]) -> None:
    manifest = load_json(repo / ".codex-plugin/plugin.json", errors)
    if "hooks" in manifest:
        fail(errors, "plugin.json still declares hooks; default discovery must not require that field")

    hooks_path = repo / "hooks/hooks.json"
    hooks_config = load_json(hooks_path, errors)
    hooks = hooks_config.get("hooks")
    if not isinstance(hooks, dict):
        fail(errors, "hooks/hooks.json must contain a top-level hooks object")
    else:
        for event in REQUIRED_EVENTS:
            groups = hooks.get(event)
            if not isinstance(groups, list) or not groups:
                fail(errors, f"hooks/hooks.json missing matcher group for {event}")
                continue
            for group in groups:
                if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                    fail(errors, f"{event}: matcher group must contain hooks array")
                    continue
                for handler in group["hooks"]:
                    if not isinstance(handler, dict) or handler.get("type") != "command":
                        fail(errors, f"{event}: handler must be a command hook")
                        continue
                    command = handler.get("command")
                    if not isinstance(command, str) or "${PLUGIN_ROOT}/hooks/" not in command:
                        fail(errors, f"{event}: command must resolve handler through ${{PLUGIN_ROOT}}")

    if not (repo / "hooks/dispatch.py").is_file():
        fail(errors, "hooks/dispatch.py is not implemented")

    try:
        package_text = (repo / "scripts/package-codex-plugin.sh").read_text(encoding="utf-8")
    except OSError as exc:
        fail(errors, f"package script: {exc}")
    else:
        archive_segment = package_text.split("git -C \"$REPO_ROOT\" -c tar.umask=0022 archive", 1)
        if len(archive_segment) != 2 or "hooks" not in archive_segment[1].split("| tar -xpf", 1)[0]:
            fail(errors, "package script does not archive hooks/")

    schema = load_json(repo / "skills/bounded-runtime-harness/assets/schemas/contract.schema.json", errors)
    task_enum = (
        schema.get("properties", {})
        .get("task_type", {})
        .get("enum", [])
        if isinstance(schema.get("properties"), dict)
        else []
    )
    if "plugin-packaging" not in task_enum:
        fail(errors, "contract schema does not admit plugin-packaging")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-only", action="store_true")
    parser.add_argument("--repo-root", type=Path)
    args = parser.parse_args()

    repo = (args.repo_root or Path(__file__).resolve().parents[2]).resolve()
    errors: list[str] = []
    corpus_sha256 = validate_corpus(repo, errors)
    print(f"corpus_sha256={corpus_sha256}")

    if args.corpus_only:
        if errors:
            for error in errors:
                print(f"FAIL {error}")
            return 1
        print("PASS frozen native-hook corpus: 21 cases (17 P1, 4 P2)")
        return 0

    validate_governance(repo, errors)
    validate_candidate_surface(repo, errors)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        print(f"RESULT fail={len(errors)}")
        return 1
    print("PASS native-hook governance, layout, and packaging admission")
    return 0


if __name__ == "__main__":
    sys.exit(main())
