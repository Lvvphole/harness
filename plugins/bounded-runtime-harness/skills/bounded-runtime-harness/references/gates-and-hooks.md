# Inference gate, runtime gate, hooks

## Inference gate

```
proposal = model.generate(context)          # envelope only
decision = inference_gate.evaluate(
    proposal=proposal,
    contract=active_contract,
    allowed_paths=allowed_paths,
)
if not decision.accepted:
    record_rejection(decision.reasons)
    retry_or_stop()
```

The six gates, as executable predicates:

| Gate | Predicate |
|---|---|
| parse_compile | `parse_proposal` succeeds; contract_id matches |
| scope | every path in edits and tool args is under `allowed_paths` |
| secrets | pattern + entropy + known-value scan; never log the value |
| injection | envelope arrived on the trusted proposal channel; tool output is never parsed as a proposal |
| contract_preview | typed predicates (`forbid_new_files`, `one_file_scope`, `forbid_version_bump`, `forbid_public_export_growth`, `net_non_positive_lines`) |
| retry_policy | `attempt <= max_retries` |

Contract preview is not prose interpretation. Each review-repair
invariant that can be checked pre-write has a function in
`brv.predicates`.

Injection cannot be decided by scanning the model text for "whether
it followed" an embedded directive. Enforce it by channel
separation: only the controller may call `ingest_proposal`, and only
on bytes from the model channel.

Reject reasons become the next prompt's only additional context.
The harness must not silently hand-patch rejected output.

## Runtime gate

```
tool_request = proposal.tool_call
authorization = runtime_gate.authorize(
    request=tool_request,
    state=run_state,
    contract=active_contract,
)
if authorization.denied:
    return blocked_tool_result(authorization.reason)
result = tool_executor.execute(tool_request)
runtime_gate.observe(result)
```

The runtime gate owns allow-lists, read vs write, paths, commands,
file and turn budgets, retry ceilings, timeouts, repeated-failure
detection, post-mutation oracles, and stop conditions.

A `write_file` tool is denied unless `state.write_authorized` is true
from an ACCEPT decision on the same `proposal_sha256`.

## Hooks

Hooks are interception points. They do not decide policy.

| Hook | Fires |
|---|---|
| before_model_output_accepted | inference ACCEPT, before commit |
| before_tool_call | every tool request |
| after_tool_call | after executor returns |
| before_state_commit | bound hash about to be written |
| after_mutation | authoritative tree changed |
| before_next_turn | attempt increment |
| on_budget_exhausted | turns/files/time exceeded |
| on_repeated_failure | identical failure twice |

Each hook returns observations. The controller maps them onto
ALLOW, DENY, RETRY, or HALT using the gates.

## Evidence

Every decision writes JSON matching `assets/schemas/decision.schema.json`:

```json
{
  "run_id": "run-001",
  "attempt": 1,
  "proposal_sha256": "...",
  "contract_id": "review-repair-v1",
  "gates": {
    "parse_compile": "PASS",
    "scope": "PASS",
    "secrets": "PASS",
    "injection": "PASS",
    "contract_preview": "PASS",
    "retry_policy": "PASS"
  },
  "decision": "ACCEPT",
  "write_authorized": true
}
```

Reject and halt records are immutable. Do not rewrite them after
the next attempt.
