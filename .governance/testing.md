# Testing commands

## Root

```bash
bash scripts/eval-governance-tree.sh .
```

## Packaged skills

```bash
bash plugins/bounded-runtime-harness/skills/bounded-runtime-harness/scripts/eval-skill.sh
bash plugins/bounded-runtime-harness/skills/governance/scripts/eval-skill.sh
python3 plugins/bounded-runtime-harness/skills/bounded-runtime-harness/assets/reference/tests/test_harness.py
```

## Manifests

```bash
python3 -c "import json; json.load(open('plugins/bounded-runtime-harness/.codex-plugin/plugin.json')); json.load(open('.agents/plugins/marketplace.json'))"
```

## Coverage thresholds

This repository does not yet publish a coverage percentage. The pass bar is exit 0 on the commands above plus the required cases inside `test_harness.py`.

## Pre-commit checks

1. `bash scripts/eval-governance-tree.sh .`
2. Parse `plugin.json` and `marketplace.json`.
3. If plugin skill files changed, run both skill eval scripts and `test_harness.py`.

## Binding table

| CONTEXT task | Contract | Oracle commands |
| --- | --- | --- |
| feature-development | `.harness/contracts/feature-development.md` | governance tree, BRH skill eval, `test_harness.py`, plugin.json parse |
| bug-fix | `.harness/contracts/bug-fix.md` | governance tree, BRH skill eval, `test_harness.py` |
| review-repair | `.harness/contracts/review-repair.md` | governance tree plus the finding's command; `git diff --name-only` must show one existing file |
| refactor | `.harness/contracts/refactor.md` | `test_harness.py`, BRH skill eval, governance tree |
| testing | `.harness/contracts/testing.md` | `test_harness.py`, BRH skill eval, governance tree |
| documentation | `.harness/contracts/documentation.md` | governance tree, plugin file existence, JSON parse |
| plugin-packaging | `.harness/contracts/plugin-packaging.md` | manifest assertions, skill SKILL.md existence, BRH skill eval |

## Regression policy

Do not "fix" a failing test unless the test is wrong. The catalog in `.harness/evals.md` owns goldens.
