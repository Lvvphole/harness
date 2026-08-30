# Bounded Runtime Harness

This repository uses structured governance files and an evaluation-first
harness to direct coding agents.

## Agent instructions
Read [AGENTS.md](./AGENTS.md) for build, test, style, and workflow rules.

## Task routing
Read [CONTEXT.md](./CONTEXT.md) for stage-specific context and contracts.

## Harness
Read `.harness/` before writing code.
- `evals.md` — goldens, metrics, thresholds
- `inference-loop.md` — accept/reject each generation
- `runtime-loop.md` — per-turn tool, budget, and sandbox gates
- `contracts/` — per-task done-when oracles

## Governance
- `security.md` — permissions, secrets, sandbox
- `testing.md` — verification commands bound to harness contracts
- `style.md` — formatting and naming
- `review-repair-invariants.md` — eight in-PR repair invariants
- `risk-register.md` — known risks and mitigations
