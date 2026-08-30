#!/usr/bin/env bash
# Evals for the governance skill itself (not a generated tree).
# Usage: eval-skill.sh [skill-dir]
set -euo pipefail

SKILL="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
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

assert "SKILL.md exists" "[[ -f \"$SKILL/SKILL.md\" ]]"
n=$(wc -l < "$SKILL/SKILL.md" | tr -d ' ')
assert "SKILL.md <= 500 lines (got $n)" "[[ $n -le 500 ]]"
assert "skill mentions evaluation-driven development" "grep -qiE 'evaluation-driven|eval-driven|EDD' \"$SKILL/SKILL.md\""
assert "skill writes harness evals first" "grep -qiE 'write .*eval|evals first|harness first' \"$SKILL/SKILL.md\""
assert "skill keeps ICM / CONTEXT routing" "grep -q 'CONTEXT.md' \"$SKILL/SKILL.md\""
assert "skill requires inference-loop.md" "grep -q 'inference-loop.md' \"$SKILL/SKILL.md\""
assert "skill requires runtime-loop.md" "grep -q 'runtime-loop.md' \"$SKILL/SKILL.md\""
assert "skill keeps 8 review-repair invariants" "grep -q 'INV-8' \"$SKILL/SKILL.md\" || grep -q 'INV-8' \"$SKILL/references/review-repair-invariants.md\""
assert "file-specs reference exists" "[[ -f \"$SKILL/references/file-specs.md\" ]]"
assert "evals-and-harness reference exists" "[[ -f \"$SKILL/references/evals-and-harness.md\" ]]"
assert "tree eval script exists" "[[ -f \"$SKILL/scripts/eval-governance-tree.sh\" ]]"
assert "description avoids colon-space" "! grep -E '^description:.*: ' \"$SKILL/SKILL.md\""
assert "description avoids angle brackets" "! grep -E '^description:.*[<>]' \"$SKILL/SKILL.md\""

echo
echo "RESULT  pass=$PASS fail=$FAIL"
if [[ $FAIL -gt 0 ]]; then
  printf '  - %s\n' "${failures[@]}"
  exit 1
fi
exit 0
