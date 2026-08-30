# Runtime loop

Apply before each tool call and at the end of each turn.

## Gates

1. **Tool permission**
   - Allow-list: read files, list directories, run the named oracles in `.governance/testing.md`, write inside allowed paths after inference-loop ACCEPT, create a feature branch, open a pull request, comment `@codex review`.
   - State-changing tools require a task type that permits mutation.
   - Force-push, delete of `.harness/` or `.governance/`, and writes to `main` are denied.

2. **Sandbox**
   - In-scope: this repository.
   - Off-limits: production credentials, other GitHub repositories unless the task names them, secret stores, and host paths outside the clone.

3. **Budget**
   - Stay inside the active contract's `max files` and `max turns`.
   - Halt when the budget is exhausted.

4. **Stop conditions**
   - Halt on contract pass.
   - Halt on review-repair invariant violation.
   - Halt on budget exhaustion.
   - Halt on repeated identical failure.

5. **Re-eval after mutation**
   - After any write under `plugins/`, run the matching `eval-skill.sh` or JSON parse.
   - After any write under `.harness/` or `.governance/`, run `bash scripts/eval-governance-tree.sh .`.
   - After any write to Python reference code or tests, run `test_harness.py`.
   - Do not batch all mutations and evaluate once if a mid-loop failure should have stopped the work.

6. **No silent tool failure**
   - A non-zero exit or empty required output is a runtime failure.
   - Do not invent oracle output.

## Terminal states

PASS, FAIL, or BLOCKED. Do not declare done from a narrative summary.
