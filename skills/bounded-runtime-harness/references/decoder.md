# Decoder constraint layer

Use the `grammar-constrained-decoding` skill for engine choice,
grammar authoring, and verification. This file only states how that
layer plugs into the bounded harness.

## What may be constrained

Constrain the candidate object or the 1.0 edit envelope, not hidden reasoning.

Preferred one-file proposal is `assets/schemas/candidate.schema.json`
(`language`, `source`, `path`). Constrained decoding governs the
object. It does not make `source` valid Python. Run
`brv.languages.parse_source` after decode.

- JSON matching `assets/schemas/candidate.schema.json` or `assets/schemas/proposal.schema.json`
- Tool name enum (`read_file | write_file | run_command | run_oracle`)
- Edit action enum (`modify | create | delete`)
- Decision status enum (`PASS | FAIL | BLOCKED`)
- Command strings from the contract allow-list when the stack can
  express that as a grammar

Prefer a lazy constraint: free reasoning, then a trigger that forces
the envelope schema.

## Engine routing (delegate, do not duplicate)

| Situation | Engine |
|---|---|
| OpenAI JSON envelope | Structured Outputs, strict schema |
| OpenAI non-JSON (unified diff body only) | Responses API custom tool + Lark |
| Local Python / HF | SynCode JSON or custom |
| vLLM / SGLang / llama.cpp | llguidance |
| ChatGPT skill with no API control | Author schema; do not claim this turn was masked |
| No decoder interface | Bounded validate-and-repair, labeled best-effort |

Read `grammar-constrained-decoding` Step 0 before adding an engine.
A markdown fence around valid JSON is not a decoder problem.

## Honesty rules

- Never say a ChatGPT UI reply was decoder-constrained by this skill.
- Never call unconstrained validate-and-repair "guaranteed."
- Verify with a parser that did not produce the bytes, even when the
  decoder is constrained. Schema conformance is not semantic
  correctness.

## Independent verification

After the model returns, parse the envelope with
`brv.envelope.parse_proposal`. That parser is the inference gate's
parse/compile oracle. Decoder success does not skip it.
