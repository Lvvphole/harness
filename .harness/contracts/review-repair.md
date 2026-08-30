# Contract: review-repair

## Hypothesis

One review finding is closed by one commit that touches one file and satisfies INV-1 through INV-8.

## Oracles

- cmd: `bash scripts/eval-governance-tree.sh .`
- expect: exit 0
- cmd: command named by the finding, typically `python3 plugins/bounded-runtime-harness/skills/bounded-runtime-harness/assets/reference/tests/test_harness.py` or a skill eval script
- expect: exit 0
- cmd: `git diff --name-only`
- expect: exactly one path, and that path already existed at the review-submitted boundary

## Invariants

- All eight invariants in `.governance/review-repair-invariants.md` apply.
- `forbid_new_files`, `one_file_scope`, `forbid_version_bump`, `forbid_public_export_growth`, and `net_non_positive_lines` are true.
- If any invariant would be violated, stop and recommend a follow-up PR.

## Budget

- max files: 1
- max turns: 8
- allowed paths: the single file named by the finding

## Done when

- The named finding is closed.
- INV-1 through INV-8 hold.
- The oracles above pass.
- Inference-loop and runtime-loop accepted the final generation.

## Not done when

- A new file appeared.
- `plugin.json` version changed.
- Multiple findings were bundled into one commit.
- The agent summarized success without command output.
