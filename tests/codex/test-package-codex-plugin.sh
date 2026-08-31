#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCRIPT_UNDER_TEST="$REPO_ROOT/scripts/package-codex-plugin.sh"

FAILURES=0
TEST_ROOT="$(mktemp -d)"
cleanup() { rm -rf "$TEST_ROOT"; }
trap cleanup EXIT

pass() { echo "  [PASS] $1"; }
fail() { echo "  [FAIL] $1"; FAILURES=$((FAILURES + 1)); }

assert_contains() {
  local haystack="$1" needle="$2" description="$3"
  if printf '%s' "$haystack" | grep -Fq -- "$needle"; then
    pass "$description"
  else
    fail "$description"
    echo "    expected to find: $needle"
  fi
}

assert_not_matches() {
  local haystack="$1" pattern="$2" description="$3"
  if printf '%s' "$haystack" | grep -Eq -- "$pattern"; then
    fail "$description"
    echo "    did not expect to match: $pattern"
  else
    pass "$description"
  fi
}

echo "Codex package archive tests"
archive="$TEST_ROOT/harness.zip"
if output="$(bash "$SCRIPT_UNDER_TEST" --allow-dirty --output "$archive" 2>&1)"; then
  pass "package script exits successfully"
else
  fail "package script exits successfully"
  printf '%s\n' "$output" | sed 's/^/      /'
fi
if [[ -f "$archive" ]]; then
  pass "package script writes archive"
else
  fail "package script writes archive"
fi
assert_contains "$output" "Archive:" "reports archive path"
assert_contains "$output" "Format:  zip" "reports zip format"
archive_paths="$(unzip -Z1 "$archive" | sed 's#/$##')"
unexpected_pattern='(^plugins/|^\.agents/|^\.harness/|^\.governance/|^scripts/|^tests/|^AGENTS\.md$|^CLAUDE\.md$|^CONTEXT\.md$)'
assert_not_matches "$archive_paths" "$unexpected_pattern" "archive excludes source-only paths"
assert_contains "$archive_paths" ".codex-plugin/plugin.json" "archive includes Codex manifest"
assert_contains "$archive_paths" "skills/governance/SKILL.md" "archive includes governance skill"
assert_contains "$archive_paths" "skills/bounded-runtime-harness/SKILL.md" "archive includes harness skill"
assert_contains "$archive_paths" "skills/governance/agents/openai.yaml" "archive includes governance metadata"
assert_contains "$archive_paths" "skills/bounded-runtime-harness/agents/openai.yaml" "archive includes harness metadata"
assert_contains "$archive_paths" "hooks/hooks.json" "archive includes hook configuration"
assert_contains "$archive_paths" "hooks/dispatch.py" "archive includes hook dispatcher"
assert_contains "$archive_paths" "README.md" "archive includes README"
assert_contains "$archive_paths" "LICENSE" "archive includes LICENSE"
if [[ "$FAILURES" -eq 0 ]]; then
  echo "All Codex package archive tests passed"
else
  echo "$FAILURES Codex package archive test(s) failed"
  exit 1
fi
