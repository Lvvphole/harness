# Harness

Repository for the Bounded Runtime Harness ChatGPT and Codex plugin.

The plugin packages the `governance` skill and the `bounded-runtime-harness` skill. Governance writes evaluation-first markdown contracts. The harness turns those contracts into an executable, fail-closed controller.

Public repository: https://github.com/Lvvphole/harness

## What this repository contains

| Path | Role |
| --- | --- |
| `plugins/bounded-runtime-harness/` | Packaged plugin (`plugin.json` + skills) |
| `.agents/plugins/marketplace.json` | Repo marketplace catalog |
| `.harness/` | Evaluation catalog, inference loop, runtime loop, task contracts |
| `.governance/` | Security, testing, style, review-repair invariants, risk register |
| `scripts/eval-governance-tree.sh` | Deterministic check that the governance tree is complete |

## Plugin structure

```
plugins/bounded-runtime-harness/
├── .codex-plugin/plugin.json
└── skills/
    ├── governance/
    └── bounded-runtime-harness/
```

Install from this repository marketplace, or copy `plugins/bounded-runtime-harness` into a personal marketplace.

## Verification

```bash
bash scripts/eval-governance-tree.sh .
bash plugins/bounded-runtime-harness/skills/bounded-runtime-harness/scripts/eval-skill.sh
python3 plugins/bounded-runtime-harness/skills/bounded-runtime-harness/assets/reference/tests/test_harness.py
```

Agent instructions start at [AGENTS.md](./AGENTS.md). Task routing is in [CONTEXT.md](./CONTEXT.md).

## Assumptions

- The empty `Lvvphole/harness` repository is the packaging home for this plugin.
- No MCP server is bundled in v1.1.0. Skills and existing host tools are sufficient for the workflow.
- Python 3 is available for the reference harness tests.
