# Contract: feature-development

## Hypothesis

A scoped feature lands in the plugin package or governance tree and every listed oracle passes.

## Oracles

- cmd: `bash scripts/eval-governance-tree.sh .`
- expect: exit 0
- cmd: `bash plugins/bounded-runtime-harness/skills/bounded-runtime-harness/scripts/eval-skill.sh`
- expect: exit 0
- cmd: `python3 plugins/bounded-runtime-harness/skills/bounded-runtime-harness/assets/reference/tests/test_harness.py`
- expect: exit 0
- cmd: `python3 -c "import json; json.load(open('plugins/bounded-runtime-harness/.codex-plugin/plugin.json'))"`
- expect: exit 0

## Invariants

- Stay inside allowed paths from `.harness/inference-loop.md`.
- Do not declare done on a proxy check.
- Do not claim ChatGPT UI decoder control.

## Budget

- max files: 20
- max turns: 30
- allowed paths: `plugins/bounded-runtime-harness/`, `.agents/plugins/`, `.harness/`, `.governance/`, `scripts/`, root identity files

## Done when

- Every oracle above has passing output in this session.
- No golden listed in `.harness/evals.md` regressed.
- Inference-loop and runtime-loop accepted the final generation.

## Not done when

- A file exists but the oracle was not run.
- Lint passed and tests were skipped.
- The agent summarized success without command output.
