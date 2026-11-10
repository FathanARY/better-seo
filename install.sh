#!/usr/bin/env bash
# Install the better-seo skill and its /seo-audit command.
#
#   ./install.sh                      # install into $HOME
#   ./install.sh --dest-root /tmp/x   # install into a sandbox root
#   ./install.sh --dry-run            # print what would happen
#
# Only writes inside <dest-root>/.{claude,codex,agents}/{skills,commands}.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/skills/better-seo"
CMD_SRC="$ROOT/commands/seo-audit.md"
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
[ -f "$CMD_SRC" ] || { echo "missing $CMD_SRC" >&2; exit 1; }

# omp reads ~/.agents/skills; Codex and Claude Code each keep their own tree.
TARGETS=(
  "$DEST_ROOT/.claude/skills/better-seo"
  "$DEST_ROOT/.codex/skills/better-seo"
  "$DEST_ROOT/.agents/skills/better-seo"
)

# Each agent scans its own commands dir for slash commands.
CMD_TARGETS=(
  "$DEST_ROOT/.claude/commands/seo-audit.md"
  "$DEST_ROOT/.codex/commands/seo-audit.md"
  "$DEST_ROOT/.omp/agent/commands/seo-audit.md"
  "$DEST_ROOT/.agents/commands/seo-audit.md"
)

if [ "$DRY" -eq 1 ]; then
  for t in "${TARGETS[@]}"; do echo "would install -> $t"; done
  for t in "${CMD_TARGETS[@]}"; do echo "would install -> $t"; done
  exit 0
fi

for t in "${TARGETS[@]}"; do
  mkdir -p "$(dirname "$t")"
  rm -rf "$t"
  cp -R "$SRC" "$t"
  # Bytecode from a local test run must never ship inside the skill.
  find "$t" -name __pycache__ -type d -prune -exec rm -rf {} +
  find "$t" -name '*.pyc' -delete
  echo "installed -> $t"
done

for t in "${CMD_TARGETS[@]}"; do
  mkdir -p "$(dirname "$t")"
  cp "$CMD_SRC" "$t"
  echo "installed -> $t"
done

echo "done. restart the agent to pick up the skill and /seo-audit."
