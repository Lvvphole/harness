---
name: governance
description: Create a governance file hierarchy for a monorepo that directs coding agents through CLAUDE.md, AGENTS.md, CONTEXT.md, plus an evaluation-first harness for runtime and inference-loop checks. Use when the user asks to set up agent governance, create a CLAUDE.md, scaffold AGENTS.md, build CONTEXT.md routing, add evals, write verification contracts, establish runtime or inference loop checks, adopt evaluation-driven development for coding agents, audit existing governance, or make a repo agent-ready.
metadata:
  version: "2.0"
  type: workflow
---

# Governance Skill

Create a governance file hierarchy that gives coding agents routing,
testing, security, and **evaluation** instructions across a monorepo.
The output is plain-text markdown any agent (Claude Code, Codex, Cursor,
Aider, Cline, or others) can read at the right moment.

ICM (Interpretable Context Methodology) remains the routing layer.
Evaluation-driven development (EDD) changes generation order and the
definition of done. The first files written are verification artifacts.
No task is complete because a file exists. A task is complete when its
oracles pass.

## Why these files matter

Agent capability is a property of the model–harness pair. The harness
reduces ambiguity, externalises memory, constrains destructive action,
and supplies corrective feedback. Evals are not a CI afterthought. They
are the harness layer that runs inside the inference loop (accept or
reject a generation) and the runtime loop (allow or halt a turn).

## Discovery interview

Before generating files, gather the following. If the conversation
already contains the answers, extract them. Do not re-ask.

1. **Repo structure** — monorepo layout, package manager, languages,
   key directories.
2. **Build and test commands** — install, build, lint, test, format —
   per package and at root. These become oracles.
3. **Branching and PR conventions** — branch names, commit format, PR
   templates.
4. **Security posture** — secrets, env vars, sandbox needs, sensitive
   paths.
5. **Agent scope** — which agents consume the files, autonomy level.
6. **Existing docs** — README, CONTRIBUTING, CI. Absorb; do not
   duplicate.
7. **Eval surface** — existing test runners, typecheckers, linters,
   schema validators, fixtures. These are the deterministic oracles.
   Note anything that today is only judged by a human or an LLM.

If the user says "just scaffold it", use defaults and flag every
assumption in a `## Assumptions` block at the end of each generated
file.

## File hierarchy

```
repo-root/
├── CLAUDE.md
├── AGENTS.md
├── CONTEXT.md
├── .harness/
│   ├── evals.md
│   ├── inference-loop.md
│   ├── runtime-loop.md
│   └── contracts/<task-type>.md
├── .governance/
│   ├── security.md
│   ├── testing.md
│   ├── style.md
│   ├── review-repair-invariants.md
│   └── risk-register.md
└── packages/<package-name>/AGENTS.md
```

Detailed specs: `references/file-specs.md`.
Harness specs: `references/evals-and-harness.md`.
Invariant text: `references/review-repair-invariants.md`.
Risk seeds: `references/risk-seed.md`.
Contract template: `assets/contract.template.md`.

## Generation process (EDD, then ICM)

Follow this order. Do not skip ahead to AGENTS.md.

### 1. Discover

Run the interview above.

### 2. Write the harness first

Create `.harness/` before any identity or routing file.

1. `.harness/evals.md` — goldens, 3–5 metrics, thresholds, which
   metrics bind to which loop. Prefer deterministic oracles.
2. `.harness/inference-loop.md` — accept/reject gates on every
   generation (parse/compile, scope, secrets, injection, contract
   preview, retry cap).
3. `.harness/runtime-loop.md` — per-turn gates (tool permission,
   sandbox, budget, stop conditions, re-eval after mutation, no silent
   tool failure).
4. `.harness/contracts/<task>.md` — one contract per task type that
   will appear in CONTEXT.md. Start from `assets/contract.template.md`.
   The first line of every contract's process is the oracle, not the
   implementation.

Read `references/evals-and-harness.md` before writing these files.

### 3. Bind commands

Write `.governance/testing.md` so every contract oracle names a
copy-pasteable command that exists in this repo.

### 4. Route with ICM

Write CONTEXT.md. Keep one-stage-one-job routing. Every task Context
block lists the harness files plus the relevant `.governance/` files.
Every task Process block starts with "confirm the oracle". Every task
Verification block points at `.harness/contracts/<task>.md`.

The `bug-fix` task must include the standalone vs review-repair router
from `references/file-specs.md`. Review-repair routes to
`.governance/review-repair-invariants.md` and
`.harness/contracts/review-repair.md`.

### 5. Operational instructions

Write AGENTS.md (≤100 lines). Include a `## Harness` section that
forbids declaring done without the active contract. Imperative voice.
Copy-pasteable commands.

### 6. Identity

Write CLAUDE.md (≤30 lines). Pointers only, including `.harness/`.

### 7. Remaining policy

Write `.governance/security.md`, `style.md`,
`review-repair-invariants.md` (verbatim from
`references/review-repair-invariants.md`), and `risk-register.md`
(seeded from `references/risk-seed.md`).

### 8. Nested package files

For each package directory, write `AGENTS.md` (≤50 lines) with setup,
tests, entry points, import boundaries, and pointers to root AGENTS.md
and `.harness/`.

### 9. Evaluate the tree

Run:

```bash
bash <this-skill>/scripts/eval-governance-tree.sh <repo-root>
```

Fix failures before presenting the tree as done. Count lines in
AGENTS.md and CLAUDE.md. If over cap, cut.

### 10. Present for review

Show the file list and any Assumptions blocks. Do not claim the repo
is agent-ready if the eval script still fails.

## ICM rules that do not change

- One stage, one job.
- Layered context loading. Load only what the current task lists.
- Plain text as the interface. No binary orchestration state.
- Every output is an edit surface.
- Nearest AGENTS.md in the directory tree wins.

EDD adds one rule on top: the first edit surface for any new task type
is its contract and oracles.

## Quality gates

Before finalizing:

- [ ] `.harness/evals.md`, `inference-loop.md`, `runtime-loop.md` exist
- [ ] Every CONTEXT.md task type has a matching `.harness/contracts/` file
- [ ] CONTEXT.md bug-fix section includes the router
- [ ] Review-repair routes to all 8 invariants and the repair contract
- [ ] AGENTS.md ≤100 lines and includes `## Harness`
- [ ] CLAUDE.md ≤30 lines and points at AGENTS.md, CONTEXT.md, `.harness/`
- [ ] testing.md commands are copy-pasteable for this stack
- [ ] security.md covers permissions, forbidden actions, secrets, sandbox
- [ ] review-repair-invariants.md has INV-1 through INV-8 and the checklist
- [ ] Nested AGENTS.md exists for each package
- [ ] `scripts/eval-governance-tree.sh <repo-root>` exits 0
- [ ] No secrets in any generated file
- [ ] Assumptions flagged where defaults were used

## Definition of done

The skill is done when:

1. A governance plus harness tree exists at the repo root.
2. An agent reading CLAUDE.md reaches AGENTS.md, CONTEXT.md,
   `.harness/`, and `.governance/` without ambiguity.
3. Evals and contracts were written before operational instructions.
4. CONTEXT.md routes at least three task types, each to a contract.
5. The bug-fix router distinguishes standalone fixes from review-repair.
6. Inference-loop and runtime-loop files define accept/reject and
   allow/halt gates that an agent can execute inside a session.
7. The eight review-repair invariants are present and enforced by the
   review-repair contract.
8. `eval-governance-tree.sh` passes against the generated tree.
9. Every file is plain markdown, human-readable, and Git-diffable.

## Testing this skill

The skill ships its own evals. Run them after any edit to the skill.

After generating a tree, run `scripts/eval-governance-tree.sh` on it.
A generation that is not scored is not finished.

## Next path — enforcement

These markdown files are policy. They do not prevent a model from
writing the worktree. When the user asks for inference-time
enforcement, transactional writes, tool-call hooks, decoder
constraints, or a controller that can HALT, load the
`bounded-runtime-harness` skill. That skill compiles these contracts
into schemas, gates, hooks, and tests that forbidden actions cannot
execute.

## Anti-patterns

- Writing AGENTS.md or CLAUDE.md before `.harness/evals.md`.
- Declaring a task done because a file appeared on disk.
- Using an LLM judge as the only oracle for a deterministic property.
- Dropping the bug-fix router or any of INV-1..INV-8.
- Exceeding the AGENTS.md or CLAUDE.md line caps.
- Duplicating README content instead of pointing at it.
- Putting operational steps in CLAUDE.md.
