# Contract: plugin-packaging

## Hypothesis

The repository root is a valid skills-and-hooks plugin that ChatGPT and Codex can load from the repo marketplace.

## Oracles

- cmd: `python3 -c "import json; m=json.load(open('.codex-plugin/plugin.json')); assert m['name']=='bounded-runtime-harness'; assert m['skills']=='./skills/'; assert 'version' in m and 'description' in m"`
- expect: exit 0
- cmd: `python3 -c "import json; c=json.load(open('.agents/plugins/marketplace.json')); assert c['plugins'][0]['source']['url']=='./'"`
- expect: exit 0
- cmd: `test -f skills/bounded-runtime-harness/SKILL.md && test -f skills/governance/SKILL.md`
- expect: exit 0
- cmd: `bash tests/codex/test-marketplace-manifest.sh`
- expect: exit 0
- cmd: `bash skills/bounded-runtime-harness/scripts/eval-skill.sh`
- expect: exit 0
- cmd: `python3 tests/codex/test_hooks.py`
- expect: exit 0

## Invariants

- Only `plugin.json` lives in `.codex-plugin/`.
- Skill directory names match SKILL.md `name` fields.
- Marketplace source is `{ "source": "url", "url": "./" }`.

## Budget

- max files: 20
- max turns: 20
- allowed paths: `.codex-plugin/`, `hooks/`, `skills/`, `.agents/plugins/`, `scripts/package-codex-plugin.sh`, `tests/codex/`, `README.md`

## Done when

- Every oracle above has passing output in this session.
- No golden in `.harness/evals.md` regressed.

## Not done when

- Manifest fields were added without a parse check.
- The agent summarized success without command output.
