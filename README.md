# Harness

Skills-only ChatGPT and Codex plugin. The repository root is the plugin.

Public repository: https://github.com/Lvvphole/harness

## What ships

The Codex/OpenAI package contains only:

```
.codex-plugin/plugin.json
skills/governance/
skills/bounded-runtime-harness/
README.md
LICENSE
```

Repo-root `.harness/`, `.governance/`, `scripts/`, and `tests/` are source-only. They are not in the portal archive.

## Install

Add this repository as a marketplace (source is `./`):

```bash
codex plugin marketplace add https://github.com/Lvvphole/harness
```

Or package a rootless archive:

```bash
bash scripts/package-codex-plugin.sh --output /tmp/harness.zip
```

## Skills

- `governance` — write the evaluation-first file tree
- `bounded-runtime-harness` — compile those contracts into a fail-closed runtime workflow

No MCP server is bundled. ChatGPT UI cannot mask the host decoder.

## Verification

```bash
bash tests/codex/test-marketplace-manifest.sh
bash tests/codex/test-package-codex-plugin.sh
bash scripts/eval-governance-tree.sh .
bash skills/bounded-runtime-harness/scripts/eval-skill.sh
bash skills/governance/scripts/eval-skill.sh
python3 skills/bounded-runtime-harness/assets/reference/tests/test_harness.py
```
