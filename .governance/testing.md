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

## Manifests and package archive

```bash
bash tests/codex/test-marketplace-manifest.sh
bash tests/codex/test-package-codex-plugin.sh
python3 tests/codex/test-native-hooks-acceptance.py
```

## Coverage thresholds

This repository does not yet publish a coverage percentage. The pass bar is exit 0 on the commands above plus the required cases inside `test_harness.py` and the frozen native-hook acceptance corpus.

## Pre-commit checks

1. `bash scripts/eval-governance-tree.sh .`
2. Parse `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`.
3. If plugin skill files changed, run both skill eval scripts and `test_harness.py`.
4. If native hooks, hook packaging, or hook policy changed, run `test-native-hooks-acceptance.py` and the package test.

## Binding table

| CONTEXT task | Contract | Oracle commands |
| --- | --- | --- |
| feature-development | `.harness/contracts/feature-development.md` | governance tree, BRH skill eval, `test_harness.py`, plugin.json parse; add native-hook acceptance when `hooks/` is in scope |
| bug-fix | `.harness/contracts/bug-fix.md` | governance tree, BRH skill eval, `test_harness.py` |
| review-repair | `.harness/contracts/review-repair.md` | governance tree plus the finding's command; `git diff --name-only` must show one existing file |
| refactor | `.harness/contracts/refactor.md` | `test_harness.py`, BRH skill eval, governance tree |
| testing | `.harness/contracts/testing.md` | `test_harness.py`, BRH skill eval, governance tree |
| documentation | `.harness/contracts/documentation.md` | governance tree, plugin file existence, JSON parse |
| plugin-packaging | `.harness/contracts/plugin-packaging.md` | manifest assertions, package archive, native-hook acceptance, installed native `hooks/list`, skill SKILL.md existence, BRH skill eval |

## Native hook verification

Codex default-discovered plugin hooks live at `<plugin-root>/hooks/hooks.json`. The source-tree oracle must verify the Codex event → matcher-group → command-handler shape and the frozen PR #14–#18 acceptance corpus. The package oracle must prove the exact archive contains the hook config and handler files.

Acceptance additionally requires installed-plugin evidence from Codex app-server `hooks/list` with plugins/hooks enabled. The expected plugin hook entries must be sourced from the installed plugin hook config with no hook parse warnings or errors. A newly discovered plugin hook may report `Untrusted` before explicit user trust; discovery and trust are separate properties.

A local JSON parser or self-defined hook schema is not a substitute for `hooks/list`. If a trusted environment capable of installing the exact artifact and returning `hooks/list` evidence is unavailable, report `BLOCKED` / `PRODUCED, NOT ACCEPTED` rather than PASS.

## Regression policy

Do not "fix" a failing test unless the test is wrong. The catalog in `.harness/evals.md` owns goldens.
