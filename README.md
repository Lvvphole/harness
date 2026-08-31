# Bounded Runtime Harness

A skills-only ChatGPT and Codex plugin that enforces governance contracts at inference time. Version 1.2.0. MIT License.

Repository: https://github.com/Lvvphole/harness

## What This Plugin Does

This plugin gives coding agents a structured governance framework and a fail-closed runtime enforcement layer.
It ships two workflow skills.
Neither skill requires an MCP server.

The **governance** skill writes an evaluation-first file tree for a repository.
It produces `CLAUDE.md`, `AGENTS.md`, `CONTEXT.md`, a `.harness/` directory, and a `.governance/` directory.
Verification artifacts (tests, oracles, contracts) come before implementation code.
A task is complete only when its oracles pass.

The **bounded-runtime-harness** skill compiles those governance contracts into an executable controller.
The controller enforces six inference gates, runtime tool authorization, and transactional worktree isolation.
It also writes immutable decision evidence.
No model output reaches the authoritative worktree unless all gates pass.

## How It Works

The enforcement flow has five steps:

1. The model emits a structured proposal envelope, not free-form edits.
2. The controller parses the proposal and applies it to a temporary worktree (a filesystem copy).
3. Six deterministic gates evaluate the proposal against the active contract.
4. On ACCEPT, the controller writes the exact verified bytes to the authoritative worktree.
5. On REJECT, the controller discards the temporary state and retries. On HALT, it preserves evidence and stops.

The decisive invariant: the bytes written to the authoritative worktree are the bytes that passed all gates.
The controller binds the proposal hash at accept time.
A commit with a different hash is refused.

## What Ships

The packaged archive contains only these paths:

```
.codex-plugin/plugin.json
skills/governance/
skills/bounded-runtime-harness/
README.md
LICENSE
```

Source-only files are excluded from the archive. These include `.harness/`, `.governance/`, `scripts/`, `tests/`, `AGENTS.md`, `CLAUDE.md`, and `CONTEXT.md`.

## Skills

### Governance (v2.0)

This skill scaffolds the governance file hierarchy for a repository.
It uses Interpretable Context Methodology (ICM) for file routing.
It uses Evaluation-Driven Development (EDD) for generation order.
The skill writes harness contracts and verification commands before it writes implementation files.
Any coding agent that reads markdown can use these files.

The skill produces these directories and files:

- `CLAUDE.md` -- project entry point for the agent.
- `AGENTS.md` -- build, test, style, and workflow rules.
- `CONTEXT.md` -- task-type routing with verification contracts.
- `.harness/` -- evaluation catalog, inference loop, runtime loop, and per-task contracts.
- `.governance/` -- security policy, testing policy, style rules, review-repair invariants, and risk register.

### Bounded Runtime Harness (v1.1)

This skill compiles governance contracts into a fail-closed execution controller. The controller owns the path between decoder constraints and authorized writes.

The controller enforces these items:

- **Proposal envelope** -- the model must emit a typed envelope, not raw edits.
- **Six inference gates** -- parse/compile, scope, secrets, injection, contract preview, and retry policy.
- **Runtime gate** -- tool authorization, allow-lists, path checks, budget limits, and stop conditions.
- **Transactional worktree** -- all edits apply to an isolated filesystem copy before the controller authorizes a write.
- **Hash-bound commits** -- the SHA-256 hash is bound at accept time. A mismatched hash is refused.
- **Immutable evidence** -- every decision (ACCEPT, REJECT, HALT) writes a JSON record that cannot be overwritten.

## Installation

### From the marketplace

Add this repository as a plugin marketplace source:

```bash
codex plugin marketplace add https://github.com/Lvvphole/harness
```

### From a local archive

Run the package script to create a rootless archive:

```bash
bash scripts/package-codex-plugin.sh --output /tmp/harness.zip
```

## Verification

Run these commands from the repository root to verify the full oracle suite:

```bash
# Governance file tree (51 assertions)
bash scripts/eval-governance-tree.sh .

# Bounded-runtime-harness skill integrity (20 assertions)
bash skills/bounded-runtime-harness/scripts/eval-skill.sh

# Governance skill integrity (13 assertions)
bash skills/governance/scripts/eval-skill.sh

# Forbidden-action and byte-identity tests (28 tests)
python3 skills/bounded-runtime-harness/assets/reference/tests/test_harness.py

# Marketplace manifest parse
bash tests/codex/test-marketplace-manifest.sh

# Plugin packaging (12 assertions)
bash tests/codex/test-package-codex-plugin.sh
```

All commands must exit with code 0 and zero failures.

## Enforcement Layers

The harness uses three enforcement layers. Each layer operates independently.

**Layer 0: Decoder constraint.**
This layer controls what tokens the model can emit.
It requires decoder controls on the host stack.
On ChatGPT UI, this layer is best-effort.
The skill authors the schema and enforces it in Layer 1.

**Layer 1: Inference gate.**
This layer evaluates a completed proposal before any write to the authoritative worktree.
Six deterministic gates run against the proposal.
A failure at any gate causes a REJECT or HALT decision.

**Layer 2: Runtime gate.**
This layer authorizes every tool request through pre-execution hooks.
It enforces allow-lists, read and write permissions, path and command restrictions, budget limits, and stop conditions.

## License

MIT. Copyright 2026 Emory Harris.
