#!/usr/bin/env bash
# install-capt-core-runtime.sh — install the capt-core-runtime skill into Hermes.
#
# Copies (never symlinks) the tracked skill package to
#   $HERMES_CONFIG_DIR/skills/capt/capt-core-runtime/
# and writes .install-provenance.json recording source repo, sha, and a content
# digest so capt-doctor.sh can detect drift.
#
# Copy, not symlink: the Hermes loader rglobs SKILL.md under the skills root; a
# symlink into a git worktree would mutate skill content on checkout and break
# on hosts without the checkout.
#
# Usage: install-capt-core-runtime.sh [--dry-run] [--dest DIR]
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/capt-core-runtime"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERMES_DIR="${HERMES_CONFIG_DIR:-$HOME/.hermes}"
DEST="$HERMES_DIR/skills/capt/capt-core-runtime"
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --dest)    DEST="${2:?}"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -f "$SRC_DIR/SKILL.md" ] || { echo "source skill not found: $SRC_DIR/SKILL.md" >&2; exit 2; }

# --- validate frontmatter against the Hermes loader contract -----------------
python3 - "$SRC_DIR/SKILL.md" <<'PY'
import re, sys
p = sys.argv[1]
text = open(p, encoding="utf-8").read()
m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
if not m:
    sys.exit("FAIL: SKILL.md must start with a YAML frontmatter block delimited by ---")
fm, body = m.group(1), m.group(2)
try:
    import yaml
    data = yaml.safe_load(fm)
except ImportError:
    data = {}
    for line in fm.splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip()
if not isinstance(data, dict):
    sys.exit("FAIL: frontmatter must be a mapping")
for key in ("name", "description"):
    if not data.get(key):
        sys.exit(f"FAIL: frontmatter missing required key: {key}")
if data["name"] != "capt-core-runtime":
    sys.exit(f"FAIL: name must be capt-core-runtime, got {data['name']}")
desc = data["description"]
if len(desc) > 1024:
    sys.exit(f"FAIL: description exceeds MAX_DESCRIPTION_LENGTH 1024 ({len(desc)})")
if len(desc) > 60:
    print(f"WARN: description is {len(desc)} chars; Hermes caps NEW skills at "
          f"SKILL_PROMPT_DESC_LIMIT=60 and truncates the prompt index")
if not body.strip():
    sys.exit("FAIL: SKILL.md body is empty")
if len(text) > 100_000:
    sys.exit(f"FAIL: SKILL.md exceeds MAX_SKILL_CONTENT_CHARS 100000 ({len(text)})")
print(f"frontmatter OK: name={data['name']} description={len(desc)}ch body={len(body)}ch")
PY

# --- refuse to install a skill that constructs a parallel runtime -----------
if grep -REn 'CAPTRuntime\(|MemoryEngine\(|MemoryUseGate\(|CTPRuntime\(|KHSB\(|LifecycleManager\(|ProofEngine\(|CapabilityRegistry\(|ClaimGuard\(|CAPTRuntime\.load' "$SRC_DIR/scripts" 2>/dev/null; then
  echo "FAIL: a script constructs a CAPT runtime component. The skill must be a loader, not a second runtime." >&2
  exit 3
fi
echo "boundary OK: no runtime construction in scripts/"

# --- provenance --------------------------------------------------------------
SRC_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo "unknown")"
SRC_BRANCH="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"
SRC_REMOTE="$(git -C "$REPO_ROOT" remote get-url origin 2>/dev/null || echo "unknown")"
SRC_DIRTY="$([ -z "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null)" ] && echo false || echo true)"

CONTENT_DIGEST="$(cd "$SRC_DIR" && find . -type f ! -name '.install-provenance.json' -print0 \
  | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
FILE_COUNT="$(cd "$SRC_DIR" && find . -type f ! -name '.install-provenance.json' | wc -l | tr -d ' ')"

echo "source:  $SRC_DIR"
echo "dest:    $DEST"
echo "sha:     $SRC_SHA ($SRC_BRANCH, dirty=$SRC_DIRTY)"
echo "digest:  $CONTENT_DIGEST  ($FILE_COUNT files)"

if [ "$DRY" = "1" ]; then echo "dry-run: nothing written"; exit 0; fi

mkdir -p "$DEST"
# copy contents, preserving the references/scripts/schemas tree
(cd "$SRC_DIR" && tar cf - .) | (cd "$DEST" && tar xf -)
chmod +x "$DEST"/scripts/*.sh 2>/dev/null || true

cat > "$DEST/.install-provenance.json" <<EOF
{
  "skill": "capt-core-runtime",
  "installed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source_repository": "$REPO_ROOT",
  "source_remote_url": "$SRC_REMOTE",
  "source_sha": "$SRC_SHA",
  "source_branch": "$SRC_BRANCH",
  "source_dirty": $SRC_DIRTY,
  "source_path": "skills/hermes/capt-core-runtime",
  "content_digest": "$CONTENT_DIGEST",
  "file_count": $FILE_COUNT,
  "installer_version": "1",
  "hermes_skills_root": "$HERMES_DIR/skills",
  "install_method": "copy"
}
EOF

echo "installed: $DEST"
echo "provenance: $DEST/.install-provenance.json"
