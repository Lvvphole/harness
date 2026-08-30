# Contract: refactor

## Hypothesis

Behavior-preserving structure change lands and every golden still passes.

## Oracles

- cmd: `python3 skills/bounded-runtime-harness/assets/reference/tests/test_harness.py`
- expect: exit 0
- cmd: `bash skills/bounded-runtime-harness/scripts/eval-skill.sh`
- expect: exit 0
- cmd: `bash scripts/eval-governance-tree.sh .`
- expect: exit 0

## Invariants

- No intentional behavior change.
- No version bump unless the task is explicitly a release.
- Public skill interface (`SKILL.md` name and trigger description) stays stable unless the task says otherwise.

## Budget

- max files: 12
- max turns: 16
- allowed paths: `skills/`, `.codex-plugin/`, `.harness/`, `scripts/`, `tests/codex/`

## Done when

- Every oracle above has passing output in this session.
- No golden in `.harness/evals.md` regressed.

## Not done when

- Tests were not run after the move.
- The agent summarized success without command output.
