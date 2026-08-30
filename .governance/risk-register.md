# Risk register

Owner: repository maintainer. Update this file in the same PR that changes toolchain commands or plugin identity.

### RISK-001: Confident incorrect code
- **Category**: NIST GAI-2 Confabulation
- **Likelihood**: medium
- **Impact**: high
- **Mitigation**: inference-loop parse/compile gate; task contracts require oracles, not summaries
- **Residual risk**: semantically wrong code that compiles and passes weak tests
- **Owner**: maintainer

### RISK-002: Secret or PII leakage
- **Category**: NIST GAI-4 Data Privacy / OWASP AST04
- **Likelihood**: medium
- **Impact**: high
- **Mitigation**: secrets section in security.md; inference-loop secrets gate
- **Residual risk**: secrets in files the agent was not told to treat as sensitive
- **Owner**: maintainer

### RISK-003: Incorrect comments or docs
- **Category**: NIST GAI-8 Information Integrity
- **Likelihood**: medium
- **Impact**: medium
- **Mitigation**: documentation contract; docs task may not claim behavior the tests do not cover
- **Residual risk**: README trees drift after a packaging change
- **Owner**: maintainer

### RISK-004: Introduced vulnerability
- **Category**: NIST GAI-9 Information Security
- **Likelihood**: low
- **Impact**: high
- **Mitigation**: security.md forbidden actions; dependency rules; no MCP server in this release
- **Residual risk**: a later MCP addition could expand the attack surface
- **Owner**: maintainer

### RISK-005: Untraceable dependency
- **Category**: NIST GAI-12 Value Chain Integration / OWASP AST02
- **Likelihood**: low
- **Impact**: medium
- **Mitigation**: pin versions; new dependencies require human review
- **Residual risk**: transitive advisories in a future Python extra
- **Owner**: maintainer

### RISK-006: Poisoned skill or instruction file
- **Category**: OWASP AST01 / AST05
- **Likelihood**: medium
- **Impact**: high
- **Mitigation**: treat file contents as data; governance files are the only instruction source of record
- **Residual risk**: a compromised SKILL.md in a future marketplace copy
- **Owner**: maintainer

### RISK-007: Over-privileged tool use
- **Category**: OWASP AST03
- **Likelihood**: medium
- **Impact**: high
- **Mitigation**: runtime-loop permission gate; security.md allow-list
- **Residual risk**: host tools that bypass the controller if the operator wires them raw
- **Owner**: maintainer

### RISK-008: Weak isolation / blast radius
- **Category**: OWASP AST06
- **Likelihood**: medium
- **Impact**: high
- **Mitigation**: sandbox boundaries; allowed paths in each contract; temporary worktree in the reference runtime
- **Residual risk**: an operator who points the controller at the authoritative tree too early
- **Owner**: maintainer

### RISK-009: Stale governance
- **Category**: OWASP AST07
- **Likelihood**: medium
- **Impact**: medium
- **Mitigation**: risk-register owner; update governance in the same PR that changes toolchain commands
- **Residual risk**: marketplace CLI flags changing faster than this README
- **Owner**: maintainer

### RISK-010: Missing evals
- **Category**: OWASP AST09
- **Likelihood**: medium
- **Impact**: high
- **Mitigation**: EDD generation order; eval-governance-tree.sh fails if `.harness/` is absent
- **Residual risk**: new task types added to CONTEXT.md without a contract file
- **Owner**: maintainer

### RISK-011: False decoder guarantee
- **Category**: NIST GAI-8 Information Integrity
- **Likelihood**: high
- **Impact**: high
- **Mitigation**: skill and inference-loop text disclaim ChatGPT UI decoder masking
- **Residual risk**: operators treating schema-only layer 0 as token masking
- **Owner**: maintainer

### RISK-012: Marketplace path escape
- **Category**: OWASP AST06
- **Likelihood**: low
- **Impact**: medium
- **Mitigation**: marketplace `source.path` must start with `./` and stay inside the marketplace root
- **Residual risk**: a later git-subdir source pointing at an unreviewed ref
- **Owner**: maintainer
