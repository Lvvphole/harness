# Contract: plugin-packaging

## Hypothesis

The repository contains a valid skills-only plugin that ChatGPT and Codex can load from the repo marketplace.

## Oracles

- cmd: `python3 -c "import json; m=json.load(open('plugins/bounded-runtime-harness/.codex-plugin/plugin.json')); assert m['name']=='bounded-runtime-harness'; assert m['skills']=='./skills/'; assert 'version' in m and 'description' in m"`
- expect: exit 0
- cmd: `python3 -c "import json; c=json.load(open('.agents/plugins/marketplace.json')); assert c['plugins'][0]['source']['path']=='./plugins/bounded-runtime-harness'"`
- expect: exit 0
- cmd: `test -f plugins/bounded-runtime-harness/skills/bounded-runtime-harness/SKILL.md && test -f plugins/bounded-runtime-harness/skills/governance/SKILL.md`
- expect: exit 0
- cmd: `bash plugins/bounded-runtime-harness/skills/bounded-runtime-harness/scripts/eval-skill.sh`
- expect: exit 0

## Invariants

- Only `plugin.json` lives in `.codex-plugin/`.
- Skill directory names match SKILL.md `name` fields.
- Marketplace `source.path` stays inside the marketplace root and starts with `./`.

## Budget

- max files: 16
- max turns: 20
- allowed paths: `plugins/bounded-runtime-harness/`, `.agents/plugins/`, `README.md`

## Done when

- Every oracle above has passing output in this session.
- No golden in `.harness/evals.md` regressed.

## Not done when

- Manifest fields were added without a parse check.
- The agent summarized success without command output.
