#!/usr/bin/env bash
set -euo pipefail
SKILL="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
PASS=0
FAIL=0
failures=()
assert() {
  local name="$1" cond="$2"
  if eval "$cond"; then
    PASS=$((PASS + 1)); echo "PASS  $name"
  else
    FAIL=$((FAIL + 1)); failures+=("$name"); echo "FAIL  $name"
  fi
}

assert "SKILL.md exists" "[[ -f \"$SKILL/SKILL.md\" ]]"
n=$(wc -l < "$SKILL/SKILL.md" | tr -d ' ')
assert "SKILL.md <= 500 lines (got $n)" "[[ $n -le 500 ]]"
assert "names decoder constraint" "grep -qi 'decoder' \"$SKILL/SKILL.md\""
assert "names inference gate" "grep -qi 'inference gate' \"$SKILL/SKILL.md\""
assert "names runtime gate" "grep -qi 'runtime gate' \"$SKILL/SKILL.md\""
assert "transactional worktree pattern" "grep -q 'TEMPORARY WORKTREE' \"$SKILL/SKILL.md\""
assert "byte-identity invariant" "grep -qi 'exact bytes' \"$SKILL/SKILL.md\""
assert "disclaims ChatGPT decoder control" "grep -qi 'cannot mask' \"$SKILL/SKILL.md\""
assert "hooks listed" "grep -q 'before_tool_call' \"$SKILL/references/gates-and-hooks.md\""
assert "proposal schema exists" "[[ -f \"$SKILL/assets/schemas/proposal.schema.json\" ]]"
assert "candidate schema exists" "[[ -f \"$SKILL/assets/schemas/candidate.schema.json\" ]]"
assert "language parser exists" "[[ -f \"$SKILL/assets/reference/brv/languages.py\" ]]"
assert "invalid-python test exists" "grep -q 'candidate_invalid_python' \"$SKILL/assets/reference/tests/test_harness.py\""
assert "decision schema exists" "[[ -f \"$SKILL/assets/schemas/decision.schema.json\" ]]"
assert "contract schema exists" "[[ -f \"$SKILL/assets/schemas/contract.schema.json\" ]]"
assert "reference controller exists" "[[ -f \"$SKILL/assets/reference/brv/controller.py\" ]]"
assert "forbidden-action tests exist" "[[ -f \"$SKILL/assets/reference/tests/test_harness.py\" ]]"
assert "description avoids colon-space" "! grep -E '^description:.*: ' \"$SKILL/SKILL.md\""
assert "description avoids angle brackets" "! grep -E '^description:.*[<>]' \"$SKILL/SKILL.md\""
GOV="$SKILL/../governance/SKILL.md"
assert "governance skill points here" "[[ -f \"$GOV\" ]] && grep -q 'bounded-runtime-harness' \"$GOV\""

echo
echo "RESULT  pass=$PASS fail=$FAIL"
if [[ $FAIL -gt 0 ]]; then
  printf '  - %s\n' "${failures[@]}"
  exit 1
fi
exit 0
