# Contract: <task-type>

## Hypothesis
<Observable claim that must become true.>

## Oracles
- cmd: `<copy-pasteable command>`
- expect: exit 0 and <named assertion>

## Invariants
- Stay inside allowed paths.
- Do not declare done on a proxy check.

## Budget
- max files:
- max turns:
- allowed paths:

## Done when
- Every oracle above has passing output in this session.
- No golden listed in `.harness/evals.md` regressed.
- Inference-loop and runtime-loop accepted the final generation.

## Not done when
- A file exists but the oracle was not run.
- Lint passed and tests were skipped.
- The agent summarized success without command output.
