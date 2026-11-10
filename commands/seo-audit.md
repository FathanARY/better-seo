---
description: Audit a site for SEO and AI-search visibility, then give a ranked fix list
argument-hint: "<url>"
---

Run a real audit of $ARGUMENTS. Do not advise from memory.

1. Locate the audit CLI. It ships inside the better-seo skill; try these in order
   and use the first that exists:

   - `~/.agents/skills/better-seo/scripts/audit.py`
   - `~/.claude/skills/better-seo/scripts/audit.py`
   - `~/.codex/skills/better-seo/scripts/audit.py`

2. Run it:

   ```bash
   python <that-path> "$ARGUMENTS" --json audit-result.json
   ```

   If the URL is missing, ask for it once and stop. If TLS fails with
   `CERTIFICATE_VERIFY_FAILED`, retry once with `--insecure` and say you did.

3. Read `score`, every `fail`, and every `warn`. Then produce:

   - **Score** and the single biggest blocker, in one line.
   - **Ranked fix list**: descending `weight`, one entry per fail/warn with what
     to change and why it costs visibility.
   - **Copy-paste fixes**: exact title tag, meta description, H1, JSON-LD block.
     Inside the limits: title 50-60 chars, description 120-155.
   - **Agentic-search gate**: whether `robots.txt` lets GPTBot, OAI-SearchBot,
     PerplexityBot and ClaudeBot fetch the audited URL, plus `llms.txt` status.
   - **Unverified**: anything you could not check. Say so instead of guessing.

4. Load `references/agentic-search.md`, `references/onpage.md` or
   `references/technical.md` from the same skill folder for the rules behind
   each recommendation. Do not dump them; cite the relevant rule.

Never invent traffic, rankings, or competitor data. Never promise a ranking or a
citation. Never recommend cloaking, hidden text, or link schemes.
