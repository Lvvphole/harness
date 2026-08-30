---
name: bounded-runtime-harness
description: Generate a bounded runtime verification harness that enforces governance contracts at decoder, inference-gate, and runtime-gate layers using transactional worktrees, event-driven hooks, and fail-closed commits. Use when the user asks to implement inference-time enforcement, pre-write hooks, tool-call authorization, proposal envelopes, byte-identity commits, circuit breakers, PASS FAIL BLOCKED termination, or to go from governance policy to an executable harness. Also use with grammar-constrained-decoding when the serving stack exposes decoder controls.
metadata:
  version: "1.1"
  type: workflow
---

# Bounded Runtime Verification Harness

Turn governance policy into a fail-closed execution controller.

The governance skill writes markdown contracts. This skill writes the
runtime that prevents model output from reaching the authoritative
worktree until those contracts pass. Policy without this layer is
instruction. This layer is enforcement.

## Relationship to other skills

- **governance** produces `.harness/*.md`, CONTEXT.md, and typed
  rules. Load it first if those files do not exist.
- **grammar-constrained-decoding** designs the decoder-constraint
  layer. Delegate engine choice to it. Do not duplicate its routing
  table.
- This skill owns the path between those two: envelope schema,
  inference gate, runtime gate, hooks, transactional worktree,
  evidence, and tests that forbidden actions cannot execute.

## What is and is not enforceable here

A ChatGPT or Codex *skill* cannot intercept hidden reasoning tokens
and cannot mask the host conversation's decoder. State that plainly.

What is enforceable in a bounded runner you control:

1. The model must emit a proposal envelope, not free-form edits.
2. The envelope is parsed, hashed, and applied only to a temporary
   worktree.
3. Six deterministic gates run against that proposal.
4. Only the exact hashed bytes may be committed.
5. Every tool call hits a pre-execution hook and an allow-list.
6. The run ends in PASS, FAIL, or BLOCKED.

On a stack with decoder controls, layer 0 additionally prevents
illegal tokens from being sampled. On ChatGPT UI, layer 0 is a
schema you author and then enforce in layer 1. Do not claim the
current chat turn was decoder-masked.

## Required execution pattern

```
LLM tokens
→ candidate schema { language, source, path }
→ language parser (AST / reject)
→ deterministic gates
→ PASS / REJECT
→ authorized writer of exact source bytes
```

Parse/compile still runs against a TEMPORARY WORKTREE or in memory.
The authoritative tree is untouched until ACCEPT.

The 1.0 multi-edit envelope remains supported. Prefer the 1.1
candidate for single-file repair. Constrained decoding, when
available, governs the candidate *object*. It does not govern
Python tokens inside `source`. `ast.parse` is mandatory.

State machine:

```
ADMIT_TASK → LOAD_CONTRACT → REQUEST_PROPOSAL
→ VALIDATE_GENERATION → AUTHORIZE_TOOL_CALL
→ EXECUTE_IN_SANDBOX → OBSERVE_RESULT
→ RUN_ORACLE → COMMIT | RETRY | HALT
```

Terminal states: PASS, FAIL, BLOCKED.

Decisive invariant: the exact bytes written to the authoritative
worktree are the exact bytes that passed all gates. Bind
`proposal_sha256` at ACCEPT. Commit refuses a different hash.

## Implementation clarifications (mandatory)

1. "Generation" means a complete structured proposal, not every
   hidden reasoning token.
2. Parse/compile runs in an isolated temporary worktree or in
   memory. Nothing touches the authoritative tree before ACCEPT.
3. Scope reads machine-readable paths from the envelope (validated
   unified diff or structured edit schema), not from prose.
4. Injection is trusted-channel separation. A heuristic scanner
   cannot decide whether the model "followed" an injected directive.
5. Contract preview is executable predicates, not interpretation of
   markdown invariants.
6. Secret scanning combines pattern detection, entropy, and
   comparison against known sensitive values, and never logs those
   values.
7. Retry requests a fresh proposal from the rejection record. Never
   silently hand-patch rejected output.
8. Acceptance binds the verified proposal bytes or diff hash.

## Discovery

If the conversation already has a governance tree, compile it. Do
not re-ask. Otherwise gather:

1. Authoritative worktree path and sandbox path.
2. Serving stack (ChatGPT UI, OpenAI API, vLLM, local HF).
3. Existing `.harness/contracts/` and `.governance/` files.
4. Tool list the agent is actually allowed to call.
5. Oracle commands from `.governance/testing.md`.

## Generation process (evals first)

### 1. Write tests that forbidden actions cannot execute

Copy and extend `assets/reference/tests/test_harness.py`. Required
cases before any controller code is considered done:

- out-of-scope path does not touch the authoritative tree
- review-repair new file is REJECT, file absent
- `write_file` denied when `write_authorized` is false
- commit with a mismatched hash raises
- invalid envelope is REJECT, not a write
- tool name outside the enum fails parse
- ACCEPT writes bytes whose hash matches `proposal_sha256`
- schema-valid candidate with invalid Python is REJECT and does not write
- candidate ACCEPT writes exact `source` bytes; `content_sha256` matches

Run them. They should fail until the runtime exists.

### 2. Install schemas

Copy `assets/schemas/*.json` to `.harness/runtime/schemas/`.

Compile each governance contract markdown file into a JSON object
matching `contract.schema.json`. Review-repair sets
`forbid_new_files`, `one_file_scope`, `forbid_version_bump`,
`forbid_public_export_growth`, and `net_non_positive_lines` to true.

### 3. Route the decoder layer

Read `references/decoder.md` and the `grammar-constrained-decoding`
skill. Write `.harness/runtime/decoder/route.md` naming the engine
and the guarantee boundary. Constrain the proposal envelope, not
chain of thought.

### 4. Install the controller

Copy `assets/reference/brv/` to `.harness/runtime/brv/`. Wire the
host's tool executor behind `Controller.authorize_and_maybe_execute`.
Do not give the model a raw write tool that bypasses the controller.

### 5. Install hooks

Register the eight hooks from `references/gates-and-hooks.md`.
Hooks emit; gates decide ALLOW, DENY, RETRY, or HALT.

### 6. Evidence

Every decision writes a JSON record matching
`decision.schema.json` under `.harness/runs/`.

### 7. Prove it

```bash
python3 assets/reference/tests/test_harness.py
```

A harness without those tests is still policy.

## Six inference gates

parse_compile, scope, secrets, injection, contract_preview,
retry_policy. Details and hook table: `references/gates-and-hooks.md`.
Architecture and state machine: `references/architecture.md`.

## Quality gates

- [ ] Forbidden-action tests exist and pass
- [ ] Byte-identity test exists and pass
- [ ] Proposal, candidate, decision, and contract schemas installed
- [ ] Language parser rejects invalid Python independently of JSON schema
- [ ] Decoder route names the engine and the guarantee boundary
- [ ] ChatGPT UI path is labeled best-effort at the decoder layer
- [ ] Temporary worktree is discarded on REJECT
- [ ] Commit refuses a hash that was not gated
- [ ] `write_file` cannot run without ACCEPT
- [ ] Evidence records are immutable JSON
- [ ] Governance review-repair predicates are compiled, not reread as prose

## Anti-patterns

- Prompting the model to "please follow inference-loop.md" and calling
  that enforcement.
- Validating after writing to the real tree, then attempting rollback.
- Scanning model text to decide injection.
- Silently editing a rejected diff so it "almost" passes.
- Claiming a ChatGPT skill masked ChatGPT's decoder.
- Using an LLM judge as the only gate.
- Letting a tool executor write files the inference gate did not bind.
