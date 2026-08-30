#!/usr/bin/env bash
# Deterministic evals for a generated governance tree.
# Usage: eval-governance-tree.sh <repo-root>
# Exit 0 only if every assertion passes.

set -euo pipefail

ROOT="${1:-}"
[[ -n "$ROOT" && -d "$ROOT" ]] || { echo "FAIL: usage: $0 <repo-root>" >&2; exit 2; }

PASS=0
FAIL=0
failures=()

assert() {
  local name="$1" cond="$2"
  if eval "$cond"; then
    PASS=$((PASS + 1))
    echo "PASS  $name"
  else
    FAIL=$((FAIL + 1))
    failures+=("$name")
    echo "FAIL  $name"
  fi
}

lines_of() { wc -l < "$1" | tr -d ' '; }

assert "CLAUDE.md exists" "[[ -f \"$ROOT/CLAUDE.md\" ]]"
assert "AGENTS.md exists" "[[ -f \"$ROOT/AGENTS.md\" ]]"
assert "CONTEXT.md exists" "[[ -f \"$ROOT/CONTEXT.md\" ]]"
assert ".harness/evals.md exists" "[[ -f \"$ROOT/.harness/evals.md\" ]]"
assert ".harness/inference-loop.md exists" "[[ -f \"$ROOT/.harness/inference-loop.md\" ]]"
assert ".harness/runtime-loop.md exists" "[[ -f \"$ROOT/.harness/runtime-loop.md\" ]]"
assert ".governance/security.md exists" "[[ -f \"$ROOT/.governance/security.md\" ]]"
assert ".governance/testing.md exists" "[[ -f \"$ROOT/.governance/testing.md\" ]]"
assert ".governance/style.md exists" "[[ -f \"$ROOT/.governance/style.md\" ]]"
assert ".governance/review-repair-invariants.md exists" "[[ -f \"$ROOT/.governance/review-repair-invariants.md\" ]]"
assert ".governance/risk-register.md exists" "[[ -f \"$ROOT/.governance/risk-register.md\" ]]"

if [[ -f "$ROOT/CLAUDE.md" ]]; then
  n=$(lines_of "$ROOT/CLAUDE.md")
  assert "CLAUDE.md <= 30 lines (got $n)" "[[ $n -le 30 ]]"
  assert "CLAUDE.md points to AGENTS.md" "grep -q 'AGENTS.md' \"$ROOT/CLAUDE.md\""
  assert "CLAUDE.md points to CONTEXT.md" "grep -q 'CONTEXT.md' \"$ROOT/CLAUDE.md\""
  assert "CLAUDE.md points to .harness" "grep -q '.harness' \"$ROOT/CLAUDE.md\""
fi

if [[ -f "$ROOT/AGENTS.md" ]]; then
  n=$(lines_of "$ROOT/AGENTS.md")
  assert "AGENTS.md <= 100 lines (got $n)" "[[ $n -le 100 ]]"
  for sec in Overview Setup Testing "Code style" "Commit and PR conventions" Security Architecture Governance Harness; do
    assert "AGENTS.md has ## $sec" "grep -qE '^## $sec' \"$ROOT/AGENTS.md\""
  done
fi

if [[ -f "$ROOT/CONTEXT.md" ]]; then
  assert "CONTEXT.md has bug-fix task" "grep -qE '^## Task: bug-fix' \"$ROOT/CONTEXT.md\""
  assert "CONTEXT.md bug-fix has Router" "grep -q '### Router' \"$ROOT/CONTEXT.md\""
  assert "CONTEXT.md routes review-repair to invariants" "grep -q 'review-repair-invariants.md' \"$ROOT/CONTEXT.md\""
  task_count=$(grep -cE '^## Task:' "$ROOT/CONTEXT.md" || true)
  assert "CONTEXT.md has >= 3 task types (got $task_count)" "[[ $task_count -ge 3 ]]"
  assert "CONTEXT.md tasks reference .harness contracts" "grep -q '.harness/contracts' \"$ROOT/CONTEXT.md\""
fi

if [[ -f "$ROOT/.governance/review-repair-invariants.md" ]]; then
  for i in 1 2 3 4 5 6 7 8; do
    assert "INV-$i present" "grep -qE \"INV-$i\" \"$ROOT/.governance/review-repair-invariants.md\""
  done
  assert "invariants enforcement checklist present" "grep -q 'Enforcement' \"$ROOT/.governance/review-repair-invariants.md\""
fi

if [[ -f "$ROOT/.harness/evals.md" ]]; then
  assert "evals.md defines metrics" "grep -qiE 'metric|threshold|golden' \"$ROOT/.harness/evals.md\""
  assert "evals.md names inference loop" "grep -q 'inference-loop' \"$ROOT/.harness/evals.md\""
  assert "evals.md names runtime loop" "grep -q 'runtime-loop' \"$ROOT/.harness/evals.md\""
fi

if [[ -f "$ROOT/.harness/inference-loop.md" ]]; then
  assert "inference-loop has accept/reject gates" "grep -qiE 'accept|reject|gate' \"$ROOT/.harness/inference-loop.md\""
  assert "inference-loop treats tool output as data" "grep -qiE 'untrusted|not instructions' \"$ROOT/.harness/inference-loop.md\""
fi

if [[ -f "$ROOT/.harness/runtime-loop.md" ]]; then
  assert "runtime-loop has tool permission gate" "grep -qiE 'permission|tool' \"$ROOT/.harness/runtime-loop.md\""
  assert "runtime-loop has stop condition" "grep -qiE 'stop|budget|halt' \"$ROOT/.harness/runtime-loop.md\""
fi

if [[ -f "$ROOT/.governance/security.md" ]]; then
  for sec in "Tool permissions" "Forbidden actions" "Secrets handling" "Sandbox"; do
    assert "security.md covers $sec" "grep -qi '$sec' \"$ROOT/.governance/security.md\""
  done
fi

secret_hits=$(grep -REn --include='*.md' \
  -e '(api[_-]?key|secret_key|password)\s*[:=]\s*['\''\"][^'\''\"]+['\''\"]' \
  -e 'AKIA[0-9A-Z]{16}' \
  -e '-----BEGIN ([A-Z]+ )?PRIVATE KEY-----' \
  "$ROOT" 2>/dev/null || true)
if [[ -n "$secret_hits" ]]; then
  FAIL=$((FAIL + 1))
  failures+=("no hardcoded secrets")
  echo "FAIL  no hardcoded secrets"
  echo "$secret_hits" | head -5
else
  PASS=$((PASS + 1))
  echo "PASS  no hardcoded secrets"
fi

if [[ -d "$ROOT/packages" ]]; then
  pkg_count=0
  missing=0
  pkg_dirs=$(find "$ROOT/packages" -mindepth 1 -maxdepth 1 -type d)
  for d in $pkg_dirs; do
    pkg_count=$((pkg_count + 1))
    if [[ ! -f "$d/AGENTS.md" ]]; then
      missing=$((missing + 1))
    fi
  done
  assert "every package has AGENTS.md ($missing missing of $pkg_count)" "[[ $missing -eq 0 && $pkg_count -gt 0 ]]"
fi

echo
echo "RESULT  pass=$PASS fail=$FAIL"
if [[ $FAIL -gt 0 ]]; then
  echo "Failed assertions:"
  printf '  - %s\n' "${failures[@]}"
  exit 1
fi
exit 0
