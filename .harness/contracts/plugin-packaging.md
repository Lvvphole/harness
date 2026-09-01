# Contract: plugin-packaging

## Hypothesis

The repository root packages as a valid Codex plugin whose source capabilities, including default-discovered native hooks when present, survive installation unchanged.

## Oracles

- cmd: `python3 -c "import json; m=json.load(open('.codex-plugin/plugin.json')); assert m['name']=='bounded-runtime-harness'; assert m['skills']=='./skills/'; assert 'version' in m and 'description' in m; assert 'hooks' not in m"`
- expect: exit 0
- cmd: `python3 -c "import json; c=json.load(open('.agents/plugins/marketplace.json')); assert c['plugins'][0]['source']['url']=='./'"`
- expect: exit 0
- cmd: `test -f skills/bounded-runtime-harness/SKILL.md && test -f skills/governance/SKILL.md`
- expect: exit 0
- cmd: `bash tests/codex/test-marketplace-manifest.sh`
- expect: exit 0
- cmd: `bash tests/codex/test-package-codex-plugin.sh`
- expect: exit 0
- cmd: `python3 tests/codex/test-native-hooks-acceptance.py`
- expect: exit 0
- cmd: `bash skills/bounded-runtime-harness/scripts/eval-skill.sh`
- expect: exit 0
- verifier: install the exact packaged artifact in a trusted Codex environment with plugins/hooks enabled and query app-server `hooks/list`
- expect: required plugin hook events are discovered from `hooks/hooks.json` with zero parse warnings/errors

## Invariants

- Only `plugin.json` lives in `.codex-plugin/`.
- Codex default hook discovery uses `<plugin-root>/hooks/hooks.json`.
- The default-discovery package does not require a `hooks` field in `plugin.json`.
- Hook JSON uses Codex's event → matcher-group → command-handler shape.
- Hook commands address packaged files through `${PLUGIN_ROOT}` rather than host-specific source paths.
- The archive includes `hooks/` whenever native hooks are present in the source candidate.
- Hook discovery and hook trust are separate: an installed hook may be discovered as `Untrusted` before explicit user trust.
- Skill directory names match SKILL.md `name` fields.
- Marketplace source is `{ "source": "url", "url": "./" }`.

## Budget

- max files: 20
- max turns: 24
- allowed paths: `.codex-plugin/`, `skills/`, `hooks/`, `.agents/plugins/`, `scripts/package-codex-plugin.sh`, `tests/codex/`, `.harness/`, `.governance/`, `README.md`, `AGENTS.md`, `CONTEXT.md`

## Done when

- Every deterministic oracle above has passing output in this session.
- The exact archive identity is recorded.
- Native `hooks/list` evidence is for that exact installed artifact and contains no hook parse warnings/errors.
- No golden in `.harness/evals.md` regressed.

## Not done when

- Manifest fields were added without a parse check.
- A local JSON parser or source-tree test is substituted for installed `hooks/list`.
- Hooks exist in the repository but are absent from the packaged artifact.
- Hook discovery is claimed from an uninstalled source tree.
- The agent summarized success without command output.
