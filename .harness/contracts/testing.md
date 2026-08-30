# Contract: testing

## Hypothesis

A new or updated deterministic oracle exists and fails for the forbidden case before it passes for the allowed case.

## Oracles

- cmd: `python3 plugins/bounded-runtime-harness/skills/bounded-runtime-harness/assets/reference/tests/test_harness.py`
- expect: exit 0
- cmd: `bash plugins/bounded-runtime-harness/skills/bounded-runtime-harness/scripts/eval-skill.sh`
- expect: exit 0
- cmd: `bash scripts/eval-governance-tree.sh .`
- expect: exit 0

## Invariants

- New tests are deterministic.
- Required forbidden-action cases in the bounded-runtime skill remain present.
- Do not delete a failing golden to obtain a pass.

## Budget

- max files: 6
- max turns: 12
- allowed paths: `**/tests/**`, `**/scripts/**`, `.harness/evals.md`, `.governance/testing.md`

## Done when

- Every oracle above has passing output in this session.
- The new case is named in `.harness/evals.md` if it is a catalog golden.

## Not done when

- A test file exists but was not executed.
- The agent summarized success without command output.
