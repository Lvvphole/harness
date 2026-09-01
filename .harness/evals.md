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
| Native hook acceptance corpus frozen | `python3 tests/codex/test-native-hooks-acceptance.py --corpus-only` | 21 cases; 17 P1 and 4 P2; exit 0 |
| Native hook source candidate accepted | `python3 tests/codex/test-native-hooks-acceptance.py` | all 21 acceptance cases plus native layout/package checks pass |
| Native installed hook discovery | Codex app-server `hooks/list` against exact installed archive | required plugin hook events; zero parse warnings/errors |

## Metrics

1. **Governance completeness** — oracle: `eval-governance-tree.sh`. Failure mode: missing routing or over-cap identity files.
2. **Skill packaging integrity** — oracle: both `eval-skill.sh` scripts. Failure mode: skill body or schemas drift from the packaged contract.
3. **Forbidden-action rejection** — oracle: `test_harness.py`. Failure mode: out-of-scope write, unauthorized `write_file`, hash-mismatched commit.
4. **Manifest validity** — oracle: JSON parse of `plugin.json` and `marketplace.json`. Failure mode: broken install identity.
5. **Line-cap compliance** — oracle: `wc -l` on `AGENTS.md` and `CLAUDE.md`. Failure mode: identity files too large to load reliably.
6. **Native hook integrity** — oracles: frozen 21-case acceptance test, packaged archive inspection, and installed `hooks/list`. Failure mode: schema drift, missing packaged hooks, policy fail-open, provenance mismatch, or plugin hooks not discovered natively.

## Thresholds

- Governance completeness: exit 0, zero failed assertions.
- Skill packaging integrity: exit 0 for both skills.
- Forbidden-action rejection: every required case in `test_harness.py` passes.
- Manifest validity: both JSON files parse; required fields `name`, `version`, `description`, `skills` present.
- Line-cap compliance: `CLAUDE.md` ≤ 30 lines; `AGENTS.md` ≤ 100 lines.
- Native hook corpus: exactly 21 frozen findings with severity split 17 P1 / 4 P2.
- Native hook candidate: every frozen source/runtime case passes; the package contains the hook config and handlers.
- Native installed discovery: exact installed artifact returns the required plugin hooks from `hooks/hooks.json` with no hook parse warnings/errors. Trust status is reported separately and may initially be `Untrusted`.

## Loop binding

- `.harness/inference-loop.md` runs parse/compile, scope, secrets, injection, and contract-preview on every generation. Metrics 4 and 5 are cheap enough for this loop.
- `.harness/runtime-loop.md` gates tool permission, sandbox path, budget, and re-eval after mutation. Metrics 1–3 run after any write that touches plugin skills, manifests, or governance files.
- Metric 6 runs whenever native hooks, hook policy, or hook packaging changes and at native-hook task completion.
- Metrics 1–3 also run at task completion. Task contracts name the exact commands.

## Regression policy

A newly failing golden blocks completion. Fix the code or packaging, not the golden, unless the golden is demonstrably wrong and the change is recorded in the PR.
