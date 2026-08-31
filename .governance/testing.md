# Testing commands

## Root

```bash
bash scripts/eval-governance-tree.sh .
```

## Packaged skills

```bash
bash skills/bounded-runtime-harness/scripts/eval-skill.sh
bash skills/governance/scripts/eval-skill.sh
python3 skills/bounded-runtime-harness/assets/reference/tests/test_harness.py
```

## Manifests, native hooks, and package archive

```bash
bash tests/codex/test-marketplace-manifest.sh
python3 tests/codex/test_hooks.py
bash tests/codex/test-package-codex-plugin.sh
```

## Coverage thresholds

This repository does not yet publish a coverage percentage. The pass bar is exit 0 on the commands above plus the required cases inside `test_harness.py` and `test_hooks.py`.

## Pre-commit checks

1. `bash scripts/eval-governance-tree.sh .`
2. Parse `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, and `hooks/hooks.json` when present.
3. If plugin skill files changed, run both skill eval scripts and `test_harness.py`.
4. If hooks or `test_hooks.py` changed, run `test_hooks.py` and the package archive test.

## Binding table

| CONTEXT task | Contract | Oracle commands |
| --- | --- | --- |
| feature-development | `.harness/contracts/feature-development.md` | governance tree, BRH skill eval, `test_harness.py`, plugin.json parse, `test_hooks.py` |
| bug-fix | `.harness/contracts/bug-fix.md` | governance tree, BRH skill eval, `test_harness.py` |
| review-repair | `.harness/contracts/review-repair.md` | governance tree plus the finding's command; `git diff --name-only` must show one existing file |
| refactor | `.harness/contracts/refactor.md` | `test_harness.py`, BRH skill eval, governance tree |
| testing | `.harness/contracts/testing.md` | `test_harness.py`, BRH skill eval, governance tree |
| documentation | `.harness/contracts/documentation.md` | governance tree, plugin file existence, JSON parse |
| plugin-packaging | `.harness/contracts/plugin-packaging.md` | manifest assertions, `test_hooks.py`, package archive, skill SKILL.md existence, BRH skill eval |

## Regression policy

Do not "fix" a failing test unless the test is wrong. The catalog in `.harness/evals.md` owns goldens.
