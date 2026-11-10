---
description: Audit a site for SEO and AI-search visibility, then give a ranked fix list
argument-hint: "<url>"
---

Run a real audit of $ARGUMENTS. Do not advise from memory.

## Step 1: resolve the audit CLI

It ships inside the skill, next to this command. `install.sh` writes an absolute
path into `@SKILL_DIR@`; a plugin manager leaves that placeholder, so the script
probes the roots plugin managers actually use, then the current directory. Run
this and use the path it prints:

```bash
CLI=""
# Some agent shells do not export HOME. Without this every probe becomes
# "/.omp/..." and silently finds nothing.
H="${HOME:-}"
[ -n "$H" ] || H="${USERPROFILE:-}"
[ -n "$H" ] || H="$(cd ~ 2>/dev/null && pwd)"
# 1. Absolute path written by install.sh (a plugin manager leaves it unsubstituted).
for c in "@SKILL_DIR@/scripts/audit.py"; do
  case "$c" in *@*) ;; *) [ -f "$c" ] && CLI="$c" ;; esac
  [ -n "$CLI" ] && break
done
# 2. Plugin roots. Two shapes: <root>/skills/better-seo/... and <root>/... .
if [ -z "$CLI" ]; then
  for root in "${PLUGIN_ROOT:-}" "${CLAUDE_PLUGIN_ROOT:-}" \
              "$H/.omp/plugins/node_modules/better-seo" \
              "$H/.agents/skills/better-seo" \
              "$H/.claude/skills/better-seo" \
              "$H/.codex/skills/better-seo"; do
    [ -n "$root" ] || continue
    for c in "$root/skills/better-seo/scripts/audit.py" "$root/scripts/audit.py"; do
      [ -f "$c" ] && CLI="$c" && break
    done
    [ -n "$CLI" ] && break
  done
fi
# 3. Current directory: a dev checkout, or the plugin tree itself.
if [ -z "$CLI" ]; then
  for c in "skills/better-seo/scripts/audit.py" "./skills/better-seo/scripts/audit.py"; do
    [ -f "$c" ] && CLI="$PWD/$c" && break
  done
fi
# 4. Versioned plugin cache, when the node_modules link is absent.
if [ -z "$CLI" ]; then
  for c in "$H"/.omp/plugins/cache/plugins/better-seo___*/skills/better-seo/scripts/audit.py; do
    [ -f "$c" ] && CLI="$c" && break
  done
fi
# 5. Last resort: search the known plugin and skill trees.
if [ -z "$CLI" ]; then
  for base in "$H/.omp/plugins" "$H/.agents" "$H/.claude" "$H/.codex"; do
    [ -d "$base" ] || continue
    c=$(find "$base" -name audit.py -path '*better-seo*' 2>/dev/null | head -1)
    [ -n "$c" ] && CLI="$c" && break
  done
fi
# Emit a path both Git Bash and native Windows Python accept. An MSYS form like
# /c/Users/x makes Windows Python look for C:\c\Users\x.
case "$CLI" in
  /*) command -v cygpath >/dev/null 2>&1 && CLI="$(cygpath -m "$CLI")" ;;
esac
echo "CLI=$CLI"
```

If it prints `CLI=` empty, say the skill is not installed and stop. Do not
substitute a guess, and do not audit with a different tool.

## Step 2: run it

```bash
python "$CLI" "<url>" --json audit-result.json
```

If the URL is missing, ask for it once and stop. If TLS fails with
`CERTIFICATE_VERIFY_FAILED`, retry once with `--insecure` and say you did.

## Step 3: report

Read `score`, every `fail`, and every `warn`. Then produce:

- **Score** and the single biggest blocker, in one line.
- **Ranked fix list**: descending `weight`, one entry per fail/warn with what to
  change and why it costs visibility.
- **Copy-paste fixes**: exact title tag, meta description, H1, JSON-LD block.
  Inside the limits: title 50-60 chars, description 120-155.
- **Agentic-search gate**: whether `robots.txt` lets GPTBot, OAI-SearchBot,
  PerplexityBot and ClaudeBot fetch the audited URL, plus `llms.txt` status.
- **Unverified**: anything you could not check. Say so instead of guessing.

## Step 4: cite the rules

Load `references/agentic-search.md`, `references/onpage.md` or
`references/technical.md` from the same skill folder for the rule behind each
recommendation. Do not dump them; cite the relevant rule.

Never invent traffic, rankings, or competitor data. Never promise a ranking or a
citation. Never recommend cloaking, hidden text, or link schemes.
