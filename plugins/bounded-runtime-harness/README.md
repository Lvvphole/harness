# Bounded Runtime Harness plugin

Skills-only ChatGPT and Codex plugin. It packages two related workflows:

1. `governance` — write the evaluation-first file tree (`CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, `.harness/`, `.governance/`).
2. `bounded-runtime-harness` — compile those contracts into a fail-closed runtime (proposal envelope, six inference gates, transactional worktree, byte-identity commit).

This plugin does not include an MCP server. ChatGPT UI cannot mask the host decoder. Decoder-layer guarantees apply only when the serving stack exposes constrained decoding.

## Layout

```
plugins/bounded-runtime-harness/
├── .codex-plugin/plugin.json
├── README.md
└── skills/
    ├── governance/
    └── bounded-runtime-harness/
```

## Local marketplace

The repository catalog lives at `.agents/plugins/marketplace.json` and points at `./plugins/bounded-runtime-harness`.

```bash
codex plugin marketplace add https://github.com/Lvvphole/harness
```

Restart the ChatGPT desktop app after adding the marketplace.

## Verify the packaged skills

```bash
bash plugins/bounded-runtime-harness/skills/bounded-runtime-harness/scripts/eval-skill.sh
python3 plugins/bounded-runtime-harness/skills/bounded-runtime-harness/assets/reference/tests/test_harness.py
bash plugins/bounded-runtime-harness/skills/governance/scripts/eval-skill.sh
```
