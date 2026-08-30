# Style

## Language settings

- Markdown: ATX headings, one H1 per file, wrapped prose.
- JSON: 2-space indent, trailing newline, no comments.
- Python: 4-space indent, `ast.parse`-valid, no unused public exports during review-repair.
- Shell: `set -euo pipefail` for eval scripts.

## Formatter and line length

- Prefer 80–100 columns for prose.
- Do not reflow entire files in a review-repair commit.
- Keep `CLAUDE.md` ≤ 30 lines and `AGENTS.md` ≤ 100 lines.

## Naming

- Plugin and skill names: kebab-case.
- Skill directory name equals SKILL.md `name`.
- Contracts: `.harness/contracts/<task-type>.md`.
- Python modules: snake_case.
- Invariants: `INV-1` through `INV-8`.
- Risks: `RISK-NNN`.

## Patterns to follow

- Evaluation-first: write the oracle before the implementation.
- One stage, one job in CONTEXT.md.
- Pointers in CLAUDE.md. Commands in AGENTS.md.
- Byte-identity commits for harness ACCEPT.

## Patterns to avoid

- Claiming ChatGPT UI masked hidden tokens.
- Putting files other than `plugin.json` in `.codex-plugin/`.
- Colon-space or angle brackets in skill `description` frontmatter.
- LLM-as-judge as the only oracle for a parse or schema property.
