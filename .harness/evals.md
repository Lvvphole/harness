# Evaluation catalog

## Principles

Evals are written before implementation. A passing proxy (file exists, command started, agent summary) is not a passing contract. New work must not regress prior goldens.

Prefer deterministic oracles: shell assertions, JSON Schema parse, Python `ast.parse`, and the reference harness test file. Do not use an LLM judge as the only oracle for a syntactic or structural property.

## Goldens

| Case | Oracle | Expected |
| --- | --- | --- |
| Governance tree complete | `bash scripts/eval-governance-tree.sh .` | exit 0 |
| Bounded-runtime skill integrity | `bash skills/bounded-runtime-harness/scripts/eval-skill.sh` | exit 0 |
| Governance skill integrity | `bash skills/governance/scripts/eval-skill.sh` | exit 0 |
| Forbidden actions cannot execute | `python3 skills/bounded-runtime-harness/assets/reference/tests/test_harness.py` | exit 0 |
| Plugin manifest parse | `python3 -c "import json; json.load(open('.codex-plugin/plugin.json'))"` | exit 0 |
| Marketplace parse | `python3 -c "import json; json.load(open('.agents/plugins/marketplace.json'))"` | exit 0 |
| Marketplace source is repo root | marketplace `plugins[0].source.url` equals `./` | boolean true |
| Plugin name is kebab-case | manifest `name` equals `bounded-runtime-harness` | boolean true |
| Skills path present | manifest `skills` equals `./skills/` | boolean true |
| Native Codex hook contract | `python3 tests/codex/test_hooks.py` | exit 0 |

## Metrics

1. **Governance completeness** — oracle: `eval-governance-tree.sh`. Failure mode: missing routing or over-cap identity files.
2. **Skill packaging integrity** — oracle: both `eval-skill.sh` scripts. Failure mode: skill body or schemas drift from the packaged contract.
3. **Forbidden-action rejection** — oracle: `test_harness.py`. Failure mode: out-of-scope write, unauthorized `write_file`, hash-mismatched commit.
4. **Manifest validity** — oracle: JSON parse of `plugin.json` and `marketplace.json`. Failure mode: broken install identity.
5. **Native hook integrity** — oracle: `test_hooks.py`. Failure mode: invalid native event wiring, fail-open authorization, host-path escape, or unbound evidence.
6. **Line-cap compliance** — oracle: `wc -l` on `AGENTS.md` and `CLAUDE.md`. Failure mode: identity files too large to load reliably.

## Thresholds

- Governance completeness: exit 0, zero failed assertions.
- Skill packaging integrity: exit 0 for both skills.
- Forbidden-action rejection: every required case in `test_harness.py` passes.
- Manifest validity: both JSON files parse; required fields `name`, `version`, `description`, `skills` present.
- Native hook integrity: every required case in `test_hooks.py` passes.
- Line-cap compliance: `CLAUDE.md` ≤ 30 lines; `AGENTS.md` ≤ 100 lines.

## Loop binding

- `.harness/inference-loop.md` runs parse/compile, scope, secrets, injection, and contract-preview on every generation. Metrics 4–6 are cheap enough for this loop.
- `.harness/runtime-loop.md` gates tool permission, sandbox path, budget, and re-eval after mutation. Metrics 1–5 run after any write that touches plugin skills, manifests, hooks, tests, or governance files as bound there.
- Metrics 1–5 also run at task completion. Task contracts name the exact commands.

## Regression policy

A newly failing golden blocks completion. Fix the code or packaging, not the golden, unless the golden is demonstrably wrong and the change is recorded in the PR.
