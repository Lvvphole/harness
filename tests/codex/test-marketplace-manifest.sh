#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MARKETPLACE="$REPO_ROOT/.agents/plugins/marketplace.json"

python3 - "$MARKETPLACE" "$REPO_ROOT" <<'PY'
import json
import sys
from pathlib import Path

marketplace_path = Path(sys.argv[1])
repo_root = Path(sys.argv[2])

marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

def assert_equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")

assert_equal(marketplace.get("name"), "harness-repo-plugins", "marketplace name")
plugins = marketplace.get("plugins")
if not isinstance(plugins, list) or not plugins:
    raise AssertionError("plugins must be a non-empty list")
plugin = plugins[0]
assert_equal(plugin.get("name"), "bounded-runtime-harness", "plugin name")
assert_equal(plugin.get("source"), {"source": "url", "url": "./"}, "plugin source")
assert_equal(
    plugin.get("policy"),
    {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
    "plugin policy",
)

manifest_path = repo_root / ".codex-plugin" / "plugin.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
assert_equal(manifest.get("name"), plugin.get("name"), "manifest name")
assert_equal(manifest.get("skills"), "./skills/", "skills path")
assert_equal("hooks" in manifest, False, "default hooks path must not be overridden")

skills_root = repo_root / "skills"
skill_dirs = sorted(p.name for p in skills_root.iterdir() if p.is_dir())
assert_equal(skill_dirs, ["bounded-runtime-harness", "governance"], "skill directories")
for name in skill_dirs:
    skill_md = skills_root / name / "SKILL.md"
    meta = skills_root / name / "agents" / "openai.yaml"
    if not skill_md.is_file():
        raise AssertionError(f"missing {skill_md}")
    if not meta.is_file():
        raise AssertionError(f"missing {meta}")

print("Codex marketplace manifest looks good")
PY
