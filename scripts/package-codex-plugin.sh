#!/usr/bin/env bash
#
# Package the harness Codex plugin as a rootless archive.
# Ships only .codex-plugin/, skills/, README.md, and LICENSE.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REF="HEAD"
OUTPUT=""
FORMAT=""
ALLOW_DIRTY=0

usage() {
  cat <<'EOF'
Usage:
  scripts/package-codex-plugin.sh [options]

Options:
  --output PATH    Write archive to PATH. Default: /tmp/harness-VERSION.zip
  --format FORMAT  zip or tar.gz. Default: zip.
  --ref REF        Git ref to package. Default: HEAD.
  --allow-dirty    Permit a dirty working tree. The archive still uses --ref.
  -h, --help       Show this help.

The archive is rootless. Source-only files (.agents, .harness, .governance,
scripts, tests, AGENTS.md, CLAUDE.md, CONTEXT.md, plugins/) are excluded.
EOF
}

die() { echo "ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT="$2"; shift 2 ;;
    --format)
      case "$2" in
        zip|tar.gz|tgz) FORMAT="$2" ;;
        *) die "--format must be zip or tar.gz" ;;
      esac
      shift 2 ;;
    --ref) REF="$2"; shift 2 ;;
    --allow-dirty) ALLOW_DIRTY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[[ -d "$REPO_ROOT/.git" ]] || die "repo root is not a git checkout: $REPO_ROOT"
command -v git >/dev/null || die "git not found"
command -v jq >/dev/null || die "jq not found"
command -v tar >/dev/null || die "tar not found"

if [[ -z "$FORMAT" ]]; then
  case "$OUTPUT" in
    *.tar.gz|*.tgz) FORMAT="tar.gz" ;;
    *) FORMAT="zip" ;;
  esac
fi
[[ "$FORMAT" == "tgz" ]] && FORMAT="tar.gz"

if [[ "$FORMAT" == "zip" ]]; then
  command -v zip >/dev/null || die "zip not found"
  command -v unzip >/dev/null || die "unzip not found"
fi

git -C "$REPO_ROOT" rev-parse --verify "$REF^{commit}" >/dev/null || die "bad ref: $REF"

if [[ "$ALLOW_DIRTY" -ne 1 ]]; then
  dirty="$(git -C "$REPO_ROOT" status --porcelain --untracked-files=all)"
  if [[ -n "$dirty" ]]; then
    printf '%s\n' "$dirty" | sed 's/^/  /' >&2
    die "working tree dirty; commit or pass --allow-dirty"
  fi
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/harness-codex-package.XXXXXX")"
STAGE="$WORK_DIR/payload"
ARCHIVE_LIST="$WORK_DIR/archive-list"
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT
mkdir -p "$STAGE"

git -C "$REPO_ROOT" -c tar.umask=0022 archive --format=tar "$REF" -- \
  .codex-plugin \
  LICENSE \
  README.md \
  skills \
  | tar -xpf - -C "$STAGE"

[[ -f "$STAGE/.codex-plugin/plugin.json" ]] || die "missing .codex-plugin/plugin.json"
[[ -d "$STAGE/skills" ]] || die "missing skills/"

VERSION="$(jq -r '.version // empty' "$STAGE/.codex-plugin/plugin.json")"
[[ -n "$VERSION" ]] || die "could not read version"

skill_count="$(find "$STAGE/skills" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
metadata_count="$(find "$STAGE/skills" -path '*/agents/openai.yaml' -type f | wc -l | tr -d ' ')"
[[ "$skill_count" == "$metadata_count" ]] || die "metadata count mismatch: $metadata_count for $skill_count skills"

if [[ -z "$OUTPUT" ]]; then
  if [[ "$FORMAT" == "zip" ]]; then
    OUTPUT="${TMPDIR:-/tmp}/harness-$VERSION.zip"
  else
    OUTPUT="${TMPDIR:-/tmp}/harness-$VERSION.tar.gz"
  fi
fi
mkdir -p "$(dirname "$OUTPUT")"
OUTPUT="$(cd "$(dirname "$OUTPUT")" && pwd)/$(basename "$OUTPUT")"

(
  cd "$STAGE"
  {
    find . -mindepth 1 -type d | sed 's#^\./##' | LC_ALL=C sort
    find . -mindepth 1 -type f | sed 's#^\./##' | LC_ALL=C sort
  } >"$ARCHIVE_LIST"
)

case "$FORMAT" in
  zip)
    TZ=UTC find "$STAGE" -exec touch -t 198001010000 {} +
    ( cd "$STAGE" && rm -f "$OUTPUT" && COPYFILE_DISABLE=1 zip -X -q - -@ <"$ARCHIVE_LIST" >"$OUTPUT" )
    archive_paths="$(unzip -Z1 "$OUTPUT" | sed 's#/$##')"
    ;;
  tar.gz)
    TZ=UTC find "$STAGE" -exec touch -t 197001010000 {} +
    ( cd "$STAGE" && rm -f "$OUTPUT" && COPYFILE_DISABLE=1 tar -czf "$OUTPUT" --no-recursion -T "$ARCHIVE_LIST" )
    archive_paths="$(tar -tzf "$OUTPUT")"
    ;;
esac

unexpected="$(printf '%s\n' "$archive_paths" | grep -E '(^plugins/|^\.agents/|^\.harness/|^\.governance/|^scripts/|^tests/|^AGENTS\.md$|^CLAUDE\.md$|^CONTEXT\.md$)' || true)"
if [[ -n "$unexpected" ]]; then
  printf '%s\n' "$unexpected" | sed 's/^/  /' >&2
  die "archive contains source-only paths"
fi

echo "Archive: $OUTPUT"
echo "Format:  $FORMAT"
echo "Version: $VERSION"
echo "Skills:  $skill_count"
