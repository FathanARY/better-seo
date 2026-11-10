#!/usr/bin/env bash
# Install the better-seo skill for Claude Code, Codex and omp.
#
#   ./install.sh                      # install into $HOME
#   ./install.sh --dest-root /tmp/x   # install into a sandbox root
#   ./install.sh --dry-run            # print what would happen
#
# Only writes inside <dest-root>/.claude/skills, <dest-root>/.codex/skills and
# <dest-root>/.agents/skills.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/better-seo"
DEST_ROOT="${HOME}"
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dest-root) DEST_ROOT="$2"; shift 2 ;;
    --dest-root=*) DEST_ROOT="${1#*=}"; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -f "$SRC/SKILL.md" ] || { echo "missing $SRC/SKILL.md" >&2; exit 1; }

# omp reads ~/.agents/skills; Codex and Claude Code each keep their own tree.
TARGETS=(
  "$DEST_ROOT/.claude/skills/better-seo"
  "$DEST_ROOT/.codex/skills/better-seo"
  "$DEST_ROOT/.agents/skills/better-seo"
)

for t in "${TARGETS[@]}"; do
  if [ "$DRY" -eq 1 ]; then
    echo "would install -> $t"
    continue
  fi
  mkdir -p "$(dirname "$t")"
  rm -rf "$t"
  cp -R "$SRC" "$t"
  echo "installed -> $t"
done

if [ "$DRY" -eq 0 ]; then
  echo "done. restart the agent to pick up the skill."
fi
