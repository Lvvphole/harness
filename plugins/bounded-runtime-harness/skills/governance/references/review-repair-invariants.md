# Review-Repair Invariants

Copy this file verbatim into `.governance/review-repair-invariants.md`
unless the repo already has a stricter local variant. Do not drop an
invariant. Do not renumber.

```markdown
# Review-Repair Invariants

These invariants govern all commits made to fix findings from a code review
within an open PR. Every fix commit must satisfy all eight. If any invariant
would be violated, stop and recommend a follow-up PR from a clean baseline.

## Governing principle

A review fix is a contraction, never an expansion. The PR's total surface
area, file count, version identity, and structure declaration must all be
less-than-or-equal after every fix commit.

## Invariants

### INV-1: No new files during review repair
A review fix cycle must not introduce files that did not exist at the
review-submitted boundary. If a fix requires a new file to prove it works,
the fix is too large for in-PR repair.

### INV-2: No increase in public surface area
A review fix must not increase the public surface area of the changed file.
No new exported functions, no new public branches, no new callable entry
points. A fix that adds surface area is a feature, not a repair.

### INV-3: Net-negative or net-zero lines changed
A correct bug fix removes wrong code and replaces it with right code. If
every fix makes the file larger, scope is expanding, not converging. Track
line counts per file across fix commits. Growth is evidence of scope breach.

### INV-4: Structure declaration must not change
The repository structure declaration (README tree, manifest, package list)
is the packaging contract. If a review fix requires updating the structure
declaration, the fix has exceeded the packaging boundary. A structure
amendment during review repair is evidence of scope breach.

### INV-5: Version identity must not change
A version bump signals a contract change. A contract change invalidates
the review that prompted the fix. If the fix requires a version bump,
it belongs in a follow-up PR against the merged baseline.

### INV-6: Revert when fix defects exceed resolved defects
When `fixes_introduced_defects >= resolved_defects`, the fix has failed
and must be reverted to the pre-fix boundary. The correct next action is
a separate, smaller PR — not another repair layer.

### INV-7: One finding, one commit, one file scope
Each review-cycle commit must name the exact finding it closes and touch
only code within that finding's scope. Bundled repairs that touch multiple
files destroy traceability and make selective revert impossible.

### INV-8: Regression tests for fixes must not require their own review
If a regression test introduces enough complexity to attract its own
findings, the test is testing the wrong abstraction. A regression test
for a review fix is a minimal reproducer — input that was wrong, now
right — not a new test framework.

## Enforcement

Before making a review-repair commit, verify:
- [ ] No new files added (INV-1)
- [ ] No new exports or public functions (INV-2)
- [ ] File line count ≤ pre-fix line count (INV-3)
- [ ] Structure declaration unchanged (INV-4)
- [ ] Version string unchanged (INV-5)
- [ ] Defects introduced by this fix < defects resolved (INV-6)
- [ ] Commit names exactly one finding, touches one file (INV-7)
- [ ] Any test added is a minimal reproducer, not new logic (INV-8)

If any check fails, do not commit. Recommend a follow-up PR instead.
```
