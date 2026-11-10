# better-seo

AI-agent skill for SEO and **agentic search** — making a site both crawlable by
classic engines and quotable by LLM answer engines (ChatGPT, Perplexity, AI
Overviews, Claude, Copilot).

Two parts: a skill the agent loads, and a stdlib-only CLI it runs before giving advice.

## Install

```bash
git clone <this-repo> && cd better-seo
./install.sh                 # writes into $HOME for all three agents
./install.sh --dest-root /tmp/x   # sandbox
./install.sh --dry-run            # show targets only
```

Targets:

| Agent | Path |
|---|---|
| Claude Code | `~/.claude/skills/better-seo` |
| Codex | `~/.codex/skills/better-seo` |
| omp | `~/.agents/skills/better-seo` |

Restart the agent afterward. The skill triggers on SEO audit requests, "why
doesn't my site rank", "why doesn't ChatGPT mention us", schema, robots.txt,
`llms.txt`, and content-brief asks.

## Audit CLI

Stdlib only, no network needed for fixtures.

```bash
python skills/better-seo/scripts/audit.py https://example.com
python skills/better-seo/scripts/audit.py https://example.com --json report.json
python skills/better-seo/scripts/audit.py --fixture page.html      # offline
python skills/better-seo/scripts/audit.py https://example.com --insecure
```

After `install.sh`, the same file lives at
`~/.agents/skills/better-seo/scripts/audit.py` (and the `.claude` / `.codex`
copies). It is self-contained: stdlib only, no imports from this repo.

Output: JSON with `score` (0-100), `checks` (id, weight, status, detail), and a
severity-sorted `issues` list.

Checks cover indexability first (a `noindex` costs 12), then title, description,
single H1, canonical, JSON-LD validity, lang, viewport, word count,
answer-first opening paragraph, heading structure, question-shaped H2s, image
alt, internal links, list/table markup, social meta, and — when online —
`robots.txt` (parsed, not just fetched: any AI crawler disallowed on the audited
URL is a `fail` worth 6 points) and `llms.txt` presence.

Exit codes: `0` audited, `2` fetch failed. `--insecure` skips TLS verification
only for machines behind a TLS-intercepting proxy; it is opt-in, never default.

## Skill contents

```
skills/better-seo/
  SKILL.md                     order of operations, guardrails, verification
  scripts/audit.py             the audit CLI, ships with the skill
  references/agentic-search.md AI crawler gates, answer-first structure, llms.txt
  references/onpage.md         title/description/heading/schema rules with numbers
  references/technical.md      crawl, render, canonical, CWV thresholds
```

## Develop

```bash
make check    # trigger match + audit behavior + install into a temp root
```

Tests are fixture-based, offline, stdlib only.

## License

MIT
