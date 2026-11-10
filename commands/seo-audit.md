---
description: Audit a site for SEO and AI-search visibility, then give a ranked fix list
argument-hint: "<url>"
---

Run a real audit of $ARGUMENTS. Do not advise from memory.

## Step 1: resolve the audit CLI

It ships inside the skill, which sits beside this command. The path is written
absolute by `install.sh`, or resolved at runtime when this arrives as a plugin.
Run this and use the path it prints:

```bash
CLI=""
for c in "@SKILL_DIR@/scripts/audit.py" \
         "${PLUGIN_ROOT:-}/skills/better-seo/scripts/audit.py" \
         "${CLAUDE_PLUGIN_ROOT:-}/skills/better-seo/scripts/audit.py" \
         "$HOME/.agents/skills/better-seo/scripts/audit.py" \
         "$HOME/.claude/skills/better-seo/scripts/audit.py" \
         "$HOME/.codex/skills/better-seo/scripts/audit.py"; do
  [ -f "$c" ] && CLI="$c" && break
done
echo "CLI=$CLI"
```

If it prints `CLI=` empty, say the skill is not installed and stop. Do not
substitute a guess.

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
