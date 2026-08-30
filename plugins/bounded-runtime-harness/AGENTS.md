# Plugin package instructions

## Setup
This directory is the plugin root. Manifest: `.codex-plugin/plugin.json`.
Skills live in `skills/governance/` and `skills/bounded-runtime-harness/`.

## Tests
- `bash skills/bounded-runtime-harness/scripts/eval-skill.sh`
- `bash skills/governance/scripts/eval-skill.sh`
- `python3 skills/bounded-runtime-harness/assets/reference/tests/test_harness.py`

## Entry points
- Skill triggers: each `skills/*/SKILL.md` frontmatter description
- Reference controller: `skills/bounded-runtime-harness/assets/reference/brv/controller.py`
- Schemas: `skills/bounded-runtime-harness/assets/schemas/`

## Import boundaries
Do not move files into `.codex-plugin/` except `plugin.json`.
Do not rename a skill directory without changing its SKILL.md `name`.

Read root [AGENTS.md](../../AGENTS.md) and `.harness/` before edits.
