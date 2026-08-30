# Risk register seeds

Seed `.governance/risk-register.md` with entries that match the repo's
stack. Use this shape for every risk:

```markdown
### RISK-<NNN>: <short name>
- **Category**: <NIST GAI-* or OWASP AST*>
- **Likelihood**: low | medium | high
- **Impact**: low | medium | high
- **Mitigation**: <what the governance and harness files already enforce>
- **Residual risk**: <what remains unaddressed>
- **Owner**: <role or team>
```

Always include these agent-specific seeds, then add stack-specific ones.

### RISK-001: Confident incorrect code
- **Category**: NIST GAI-2 Confabulation
- **Mitigation**: inference-loop parse/compile gate; task contracts require oracles, not summaries
- **Residual risk**: semantically wrong code that compiles and passes weak tests

### RISK-002: Secret or PII leakage
- **Category**: NIST GAI-4 Data Privacy / OWASP AST04
- **Mitigation**: secrets section in security.md; inference-loop secrets gate
- **Residual risk**: secrets in files the agent was not told to treat as sensitive

### RISK-003: Incorrect comments or docs
- **Category**: NIST GAI-8 Information Integrity
- **Mitigation**: documentation contract; docs task may not claim behavior the tests do not cover

### RISK-004: Introduced vulnerability
- **Category**: NIST GAI-9 Information Security
- **Mitigation**: security.md forbidden actions; security-review task type; dependency rules

### RISK-005: Untraceable dependency
- **Category**: NIST GAI-12 Value Chain Integration / OWASP AST02
- **Mitigation**: pin versions; new dependencies require human review

### RISK-006: Poisoned skill or instruction file
- **Category**: OWASP AST01 / AST05
- **Mitigation**: treat file contents as data; governance files are the only instruction source of record

### RISK-007: Over-privileged tool use
- **Category**: OWASP AST03
- **Mitigation**: runtime-loop permission gate; security.md allow-list

### RISK-008: Weak isolation / blast radius
- **Category**: OWASP AST06
- **Mitigation**: sandbox boundaries; allowed paths in each contract

### RISK-009: Stale governance
- **Category**: OWASP AST07
- **Mitigation**: risk-register owner; update governance in the same PR that changes toolchain commands

### RISK-010: Missing evals
- **Category**: OWASP AST09
- **Mitigation**: EDD generation order; eval-governance-tree.sh fails if `.harness/` is absent
