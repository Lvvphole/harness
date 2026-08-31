# Context Routing

## How to use this file

Read this file to decide which context to load. Each section defines a task type, its inputs, its process, its outputs, and its verification contract. Load only the files listed under Context.

## Task: feature-development

### Context

- Harness: `.harness/evals.md`, `.harness/inference-loop.md`, `.harness/runtime-loop.md`, `.harness/contracts/feature-development.md`
- Policy: `.governance/testing.md`, `.governance/security.md`, `.governance/style.md`
- Working: `hooks/`, `skills/`, `.codex-plugin/`, `.agents/plugins/`, `.harness/`, `.governance/`, `scripts/`, `tests/codex/`

### Process

1. Confirm the oracle in `.harness/contracts/feature-development.md`.
2. Add or extend a failing golden before writing feature code.
3. Implement inside allowed paths.
4. Re-run the contract oracles after mutation.

### Outputs

Feature files under the plugin package or governance tree, plus updated goldens when behavior is new.

### Verification

Satisfy `.harness/contracts/feature-development.md`. Do not accept a proxy.

## Task: bug-fix

### Router

Before writing any code, determine which sub-type applies:

1. **Standalone bug fix** (new PR from main):
   - Context: `.harness/contracts/bug-fix.md`, `.governance/testing.md`
   - Process: write failing test → fix code → verify full suite
   - No constraints on file count or surface area

2. **Review-repair fix** (fixing findings within an open PR):
   - Context: `.harness/contracts/review-repair.md`, `.governance/review-repair-invariants.md`, `.governance/testing.md`
   - Process: one finding → one commit → one file scope
   - All 8 review-repair invariants apply
   - If any invariant would be violated, STOP and recommend a follow-up PR

The router exists because review-repair fixes masquerading as standalone bug fixes are the primary cause of scope explosion in review cycles. Classify before acting.

### Context

- Harness: `.harness/evals.md`, `.harness/inference-loop.md`, `.harness/runtime-loop.md`, `.harness/contracts/bug-fix.md`
- Policy: `.governance/testing.md`, `.governance/security.md`
- Working: the files named by the failing oracle

### Process

1. Confirm the oracle.
2. Classify standalone vs review-repair.
3. Reproduce the failure.
4. Fix only after the failure is visible.
5. Run the full suite.

### Outputs

A fix commit whose message names the defect.

### Verification

Satisfy `.harness/contracts/bug-fix.md`. Do not accept a proxy.

## Task: review-repair

### Context

- Harness: `.harness/evals.md`, `.harness/inference-loop.md`, `.harness/runtime-loop.md`, `.harness/contracts/review-repair.md`
- Policy: `.governance/review-repair-invariants.md`, `.governance/testing.md`, `.governance/security.md`
- Working: the single file named by the finding

### Process

1. Confirm the oracle.
2. Read INV-1 through INV-8.
3. Repair one finding in one file.
4. Stop if a new file, version bump, or structure-declaration change would be required.

### Outputs

One commit that names the finding.

### Verification

Satisfy `.harness/contracts/review-repair.md`. Do not accept a proxy.

## Task: refactor

### Context

- Harness: `.harness/evals.md`, `.harness/inference-loop.md`, `.harness/runtime-loop.md`, `.harness/contracts/refactor.md`
- Policy: `.governance/style.md`, `.governance/testing.md`
- Working: `skills/`, `.codex-plugin/`, `.harness/`, `scripts/`, `tests/codex/`

### Process

1. Confirm the oracle.
2. Record current suite status.
3. Restructure without changing observable behavior.
4. Re-run the suite.

### Outputs

Behavior-preserving file moves or internal cleanups.

### Verification

Satisfy `.harness/contracts/refactor.md`. Do not accept a proxy.

## Task: testing

### Context

- Harness: `.harness/evals.md`, `.harness/inference-loop.md`, `.harness/runtime-loop.md`, `.harness/contracts/testing.md`
- Policy: `.governance/testing.md`
- Working: `**/tests/**`, `**/scripts/**`, `.harness/evals.md`

### Process

1. Confirm the oracle.
2. Add the forbidden case first.
3. Confirm it fails for the wrong behavior and passes for the right behavior.
4. Register catalog goldens in `.harness/evals.md` when they are durable.

### Outputs

Deterministic tests and updated catalog rows.

### Verification

Satisfy `.harness/contracts/testing.md`. Do not accept a proxy.

## Task: documentation

### Context

- Harness: `.harness/evals.md`, `.harness/inference-loop.md`, `.harness/runtime-loop.md`, `.harness/contracts/documentation.md`
- Policy: `.governance/style.md`, `.governance/testing.md`
- Working: `README.md`, `CONTEXT.md`

### Process

1. Confirm the oracle.
2. Diff documentation against the files on disk.
3. Remove claims the tests do not cover.

### Outputs

Accurate README and routing text.

### Verification

Satisfy `.harness/contracts/documentation.md`. Do not accept a proxy.

## Task: plugin-packaging

### Context

- Harness: `.harness/evals.md`, `.harness/inference-loop.md`, `.harness/runtime-loop.md`, `.harness/contracts/plugin-packaging.md`
- Policy: `.governance/testing.md`, `.governance/security.md`
- Working: `.codex-plugin/`, `hooks/`, `skills/`, `.agents/plugins/`, `scripts/package-codex-plugin.sh`, `tests/codex/`

### Process

1. Confirm the oracle.
2. Keep `.codex-plugin/plugin.json` as the only file in `.codex-plugin/`.
3. Keep skill folder names aligned with SKILL.md `name` fields.
4. Validate `hooks/hooks.json` and its native event wire contract.
5. Parse both JSON manifests after every edit.

### Outputs

A loadable skills-and-hooks plugin and a valid repo marketplace entry.

### Verification

Satisfy `.harness/contracts/plugin-packaging.md`. Do not accept a proxy.
