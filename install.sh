#!/usr/bin/env bash
# Install the better-seo skills and their slash commands.
#
#   ./install.sh                      # install into $HOME
#   ./install.sh --dest-root /tmp/x   # install into a sandbox root
#   ./install.sh --dry-run            # print what would happen
#
# Only writes inside <dest-root>/.{claude,codex,agents}/{skills,commands} and
# <dest-root>/.omp/agent/commands.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIT_SRC="$ROOT/skills/better-seo"
BUILD_SRC="$ROOT/skills/better-seo-build"
DEST_ROOT="${HOME}"
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --dest-root) DEST_ROOT="$2"; shift 2 ;;
    --dest-root=*) DEST_ROOT="${1#*=}"; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[ -f "$AUDIT_SRC/SKILL.md" ] || { echo "missing $AUDIT_SRC/SKILL.md" >&2; exit 1; }
[ -f "$BUILD_SRC/SKILL.md" ] || { echo "missing $BUILD_SRC/SKILL.md" >&2; exit 1; }

# omp reads ~/.agents/skills; Codex and Claude Code each keep their own tree.
SKILL_ROOT_TARGETS=(
  "$DEST_ROOT/.claude/skills"
  "$DEST_ROOT/.codex/skills"
  "$DEST_ROOT/.agents/skills"
)

# Each agent scans its own commands dir for slash commands. A command body
# embeds an absolute path to its skill, so every copy is written against the
# skill tree that same agent actually loads.
#   <command file> | <command path> | <skill dir that agent loads>
CMD_TARGETS=(
  "seo-audit.md|$DEST_ROOT/.claude/commands/seo-audit.md|$DEST_ROOT/.claude/skills/better-seo"
  "seo-audit.md|$DEST_ROOT/.codex/commands/seo-audit.md|$DEST_ROOT/.codex/skills/better-seo"
  "seo-audit.md|$DEST_ROOT/.omp/agent/commands/seo-audit.md|$DEST_ROOT/.agents/skills/better-seo"
  "seo-audit.md|$DEST_ROOT/.agents/commands/seo-audit.md|$DEST_ROOT/.agents/skills/better-seo"
  "seo-build.md|$DEST_ROOT/.claude/commands/seo-build.md|$DEST_ROOT/.claude/skills/better-seo-build"
  "seo-build.md|$DEST_ROOT/.codex/commands/seo-build.md|$DEST_ROOT/.codex/skills/better-seo-build"
  "seo-build.md|$DEST_ROOT/.omp/agent/commands/seo-build.md|$DEST_ROOT/.agents/skills/better-seo-build"
  "seo-build.md|$DEST_ROOT/.agents/commands/seo-build.md|$DEST_ROOT/.agents/skills/better-seo-build"
)

if [ "$DRY" -eq 1 ]; then
  for r in "${SKILL_ROOT_TARGETS[@]}"; do
    echo "would install -> $r/better-seo"
    echo "would install -> $r/better-seo-build"
  done
  for pair in "${CMD_TARGETS[@]}"; do echo "would install -> $(echo "$pair" | cut -d'|' -f2)"; done
  exit 0
fi

prune() {
  # Bytecode from a local test run must never ship inside a skill.
  find "$1" -name __pycache__ -type d -prune -exec rm -rf {} +
  find "$1" -name '*.pyc' -delete
}

for base in "${SKILL_ROOT_TARGETS[@]}"; do
  mkdir -p "$base"
  for pair in "better-seo:$AUDIT_SRC" "better-seo-build:$BUILD_SRC"; do
    name="${pair%%:*}"
    src="${pair#*:}"
    dst="$base/$name"
    rm -rf "$dst"
    cp -R "$src" "$dst"
    prune "$dst"
    echo "installed -> $dst"
  done
  # The build skill reuses the audit skill's reference files. Copying them at
  # install time keeps one source of truth in the repo while leaving each
  # installed skill self-contained.
  ref_src="$base/better-seo/references"
  ref_dst="$base/better-seo-build/references"
  if [ -d "$ref_src" ]; then
    rm -rf "$ref_dst"
    cp -R "$ref_src" "$ref_dst"
  fi
done

for triple in "${CMD_TARGETS[@]}"; do
  file="${triple%%|*}"
  rest="${triple#*|}"
  cmd="${rest%%|*}"
  skill_dir="${rest#*|}"
  # The path lands inside a shell snippet with forward slashes: backslashes would
  # be eaten by the shell that runs it.
  skill_dir="${skill_dir//\\//}"
  # Git Bash hands out MSYS paths like /c/Users/x and /tmp/x. Native Windows
  # Python reads those as C:\c\Users\x, so convert any absolute POSIX path to
  # mixed form C:/Users/x, which both the shell and Windows Python accept.
  case "$skill_dir" in
    /*) if command -v cygpath >/dev/null 2>&1; then
          skill_dir="$(cygpath -m "$skill_dir")"
        fi ;;
  esac
  mkdir -p "$(dirname "$cmd")"
  # Bash parameter expansion is a literal replacement; sed would treat the
  # backslashes in a Windows path as escapes and mangle the path.
  body="$(<"$ROOT/commands/$file")"
  printf '%s\n' "${body//@SKILL_DIR@/$skill_dir}" > "$cmd"
  echo "installed -> $cmd"
done

echo "done. restart the agent to pick up the skills, /seo-audit and /seo-build."
