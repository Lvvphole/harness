# Architecture

Governance files are policy. This skill produces the execution path
that makes that policy fail-closed.

```
governance markdown          decoder constraint
CONTEXT + .harness/policy    grammar / JSON schema / tool enum
        \                    /
         \                  /
          typed contract + proposal envelope
                      |
              bounded controller
         ADMIT → LOAD_CONTRACT → REQUEST_PROPOSAL
         → VALIDATE_GENERATION → AUTHORIZE_TOOL_CALL
         → EXECUTE_IN_SANDBOX → OBSERVE_RESULT
         → RUN_ORACLE → COMMIT | RETRY | HALT
                      |
              PASS | FAIL | BLOCKED
```

## Three enforcement layers

1. **Decoder constraint** — controls what the model can emit, if and
   only if the serving stack exposes decoder controls. Route through
   the `grammar-constrained-decoding` skill. A ChatGPT-hosted skill
   cannot mask ChatGPT's decoder. Author the schema anyway; enforce
   it after the fact with the inference gate.

2. **Inference gate** — evaluates a completed proposal before any
   authoritative write. This is the output guardrail / policy
   enforcement point.

3. **Runtime gate** — authorizes every tool request through
   pre-execution hooks. Hooks intercept. The deterministic policy
   engine decides ALLOW, DENY, RETRY, or HALT.

## Required execution pattern

```
MODEL OUTPUT
→ PARSE PROPOSAL ENVELOPE
→ APPLY DIFF TO TEMPORARY WORKTREE
→ RUN SIX GATES
→ ACCEPT: apply verified diff to real worktree
→ REJECT: discard temporary state and retry
→ HALT: preserve evidence and stop
```

## Decisive invariant

The exact bytes written to the authoritative worktree must be the
exact bytes that passed all gates. Bind `proposal_sha256` at accept
time. `commit(sha)` refuses a different hash.

## Generation is a proposal, not a token

"Generation" means a complete structured proposal envelope. Hidden
reasoning tokens are out of band. Standard ChatGPT and Codex skills
cannot intercept hidden inference. Constrain the tool payload or the
final JSON envelope, not the chain of thought.

## What this skill emits into a repo

```
.harness/runtime/
├── schemas/          proposal, decision, contract
├── grammars/         optional Lark for the envelope
├── decoder/route.md  engine routing + honesty about guarantees
├── brv/              controller, gates, hooks, worktree, evidence
└── tests/            forbidden-action and byte-identity tests
```

Policy markdown from the governance skill stays in `.harness/*.md`
and `.governance/`. This skill compiles those documents into the
typed contract the controller loads.
