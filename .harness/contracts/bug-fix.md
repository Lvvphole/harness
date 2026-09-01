# Contract: bug-fix

## Hypothesis

A failing golden or test is reproduced first, then the defect is fixed, then the full suite passes.

## Oracles

- cmd: `bash scripts/eval-governance-tree.sh .`
- expect: exit 0
- cmd: `bash skills/bounded-runtime-harness/scripts/eval-skill.sh`
- expect: exit 0
- cmd: `python3 skills/bounded-runtime-harness/assets/reference/tests/test_harness.py`
- expect: exit 0
- cmd: `python3 tests/codex/test_hooks.py` when hooks are affected
- expect: exit 0

## Invariants

- Write or confirm a failing oracle before changing production files.
- Do not weaken a golden to obtain green output.
- Standalone bug fixes have no file-count cap. Review-repair is a different contract.

## Budget

- max files: unlimited for standalone fixes
- max turns: 24
- allowed paths: paths named by the failing oracle and its direct fixtures

## Done when

- The originally failing oracle now passes.
- The full suite above passes.
- No golden in `.harness/evals.md` regressed.

## Not done when

- The agent edited code without first showing the failing oracle.
- Tests were skipped after the edit.
- The agent summarized success without command output.
