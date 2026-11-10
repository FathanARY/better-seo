# better-seo

AI-agent skill for SEO and **agentic search** — making a site both crawlable by
classic engines and quotable by LLM answer engines (ChatGPT, Perplexity, AI
Overviews, Claude, Copilot).

Two parts: a skill the agent loads, and a stdlib-only CLI it runs before giving advice.

## Install

```bash
git clone https://github.com/FathanARY/better-seo.git && cd better-seo
./install.sh                      # writes into $HOME for all three agents
./install.sh --dest-root /tmp/x   # sandbox
./install.sh --dry-run            # show targets only
```

On Windows, `./install.sh` cannot run (Windows has no shebang exec). Use a real
bash, not the WSL stub that often sits on `PATH`:

```bash
"C:/Program Files/Git/bin/bash.exe" install.sh --dry-run
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

## Slash command

```
/seo-audit https://example.com
```

Installed per agent. Each copy hardcodes the absolute path of the skill tree
that same agent loads, so it runs the right CLI even with several installs on
the box:

| Consumer | Path |
|---|---|
| Claude Code | `~/.claude/commands/seo-audit.md` |
| omp (native provider) | `~/.omp/agent/commands/seo-audit.md` |
| omp (agents provider) | `~/.agents/commands/seo-audit.md` |
| Codex via omp's `codex` provider | `~/.codex/commands/seo-audit.md` |

Native Codex has no slash-command surface for this: OpenAI deprecated custom
prompts in favour of skills, so Codex is covered by the skill itself.

The command runs `audit.py` and returns a score, a severity-ranked fix list,
copy-paste-ready markup, and the agentic-search gate verdict. It refuses to
advise without running the audit.

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

Tests are fixture-based, offline, stdlib only. `make check` runs `make clean`
first, so local bytecode can never ride along into an installed skill.

## License

MIT
