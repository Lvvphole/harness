# Contract: feature-development

## Hypothesis

A scoped feature lands in the plugin package or governance tree and every listed oracle passes.

## Oracles

- cmd: `bash scripts/eval-governance-tree.sh .`
- expect: exit 0
- cmd: `bash skills/bounded-runtime-harness/scripts/eval-skill.sh`
- expect: exit 0
- cmd: `python3 skills/bounded-runtime-harness/assets/reference/tests/test_harness.py`
- expect: exit 0
- cmd: `python3 -c "import json; json.load(open('.codex-plugin/plugin.json'))"`
- expect: exit 0
- cmd: `python3 tests/codex/test_hooks.py` when hooks are affected
- expect: exit 0

## Invariants

- Stay inside allowed paths from `.harness/inference-loop.md`.
- Do not declare done on a proxy check.
- Do not claim ChatGPT UI decoder control.

## Budget

- max files: 20
- max turns: 30
- allowed paths: `hooks/`, `skills/`, `.codex-plugin/`, `.agents/plugins/`, `.harness/`, `.governance/`, `scripts/`, `tests/codex/`, root identity files

## Done when

- Every oracle above has passing output in this session.
- No golden listed in `.harness/evals.md` regressed.
- Inference-loop and runtime-loop accepted the final generation.

## Not done when

- A file exists but the oracle was not run.
- Lint passed and tests were skipped.
- The agent summarized success without command output.
