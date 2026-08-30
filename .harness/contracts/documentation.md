# Contract: documentation

## Hypothesis

Documentation matches repository layout and does not claim behavior the oracles do not cover.

## Oracles

- cmd: `bash scripts/eval-governance-tree.sh .`
- expect: exit 0
- cmd: `test -f .codex-plugin/plugin.json && test -f .agents/plugins/marketplace.json && test -f skills/governance/SKILL.md && test -f skills/bounded-runtime-harness/SKILL.md`
- expect: exit 0
- cmd: `python3 -c "import json; json.load(open('.codex-plugin/plugin.json')); json.load(open('.agents/plugins/marketplace.json'))"`
- expect: exit 0

## Invariants

- Docs may not claim ChatGPT UI decoder masking.
- Docs may not invent an MCP server that is not packaged.
- Structure trees in README files must match the files on disk.

## Budget

- max files: 8
- max turns: 10
- allowed paths: `README.md`, `CONTEXT.md`, `.harness/evals.md`, `LICENSE`

## Done when

- Every oracle above has passing output in this session.
- No golden in `.harness/evals.md` regressed.

## Not done when

- The README tree disagrees with `find`.
- The agent summarized success without command output.
