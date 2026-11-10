# better-seo

AI-agent skill for SEO and **agentic search** — making a site both crawlable by
classic engines and quotable by LLM answer engines (ChatGPT, Perplexity, AI
Overviews, Claude, Copilot).

Two skills and two commands:

| Skill | Command | Does |
|---|---|---|
| `better-seo` | `/seo-audit <url>` | Measures a page or the whole site: 18 checks, score 0-100, ranked fixes |
| `better-seo-build` | `/seo-build` | Configures SEO into a project that has none: robots, sitemap, llms.txt, canonical, meta, JSON-LD |

Audit measures. Build scaffolds. Neither invents the site's facts.

Ships two ways: as a **plugin** for agents with a plugin manager, and as a
plain skill tree for everyone else. Either path gives you both skills, both
stdlib CLIs, and both commands.

## Install as a plugin

The repo is its own marketplace, with a manifest per platform. No `install.sh`,
no copying into `$HOME`.

**omp**

```bash
omp plugin marketplace add FathanARY/better-seo
omp plugin install better-seo@better-seo
```

Or link a local checkout while developing:

```bash
omp plugin link .          # needs package.json, which the repo has
```

**Claude Code** — manifests in `.claude-plugin/`:

```bash
claude plugin marketplace add FathanARY/better-seo
claude plugin install better-seo@better-seo
```

**Codex** — `.codex-plugin/plugin.json`.

Manifests present: `plugin.json` (portable Agent Plugins 1.0.0), `.claude-plugin/`,
`.codex-plugin/`, `.omp-plugin/`, `.agents/plugins/`, plus `package.json` for
`omp plugin link`. `make check` validates they agree on name, version, content
paths, and that the portable manifest satisfies its closed schema.

## Install as a skill tree

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

Writes into `$HOME` for every agent. Use this when there is no plugin manager,
or when you want a sandbox (`--dest-root`) or a preview (`--dry-run`).

Targets:

| Agent | Path |
|---|---|
| Claude Code | `~/.claude/skills/better-seo` |
| Codex | `~/.codex/skills/better-seo` |
| omp | `~/.agents/skills/better-seo` |

Restart the agent afterward. The skill triggers on SEO audit requests, "why
doesn't my site rank", "why doesn't ChatGPT mention us", schema, robots.txt,
`llms.txt`, and content-brief asks.

## Slash commands

```
/seo-audit https://example.com      # score a live page, get ranked fixes
/seo-build                          # scaffold SEO into the current project
```

### `/seo-build`

Detects the project's framework from files that are actually there, then writes
native config where the framework has one:

| Framework | Artifacts |
|---|---|
| Next.js App Router | `app/robots.ts`, `app/sitemap.ts`, `lib/seo.ts` |
| Astro | `src/pages/sitemap.xml.ts`, `Seo.astro`, `public/robots.txt` |
| SvelteKit | `src/routes/sitemap.xml/+server.ts`, `static/robots.txt` |
| Nuxt | `server/routes/sitemap.xml.ts`, `useSeo` composable |
| Hugo / Jekyll | `layouts/partials/seo.html`, `_includes/seo.html` |
| Static / unknown | `robots.txt`, `sitemap.xml`, `llms.txt`, `seo-head.html` |

Dry-run by default; `--write` applies. It never overwrites an existing file, and
`--inject page.html` merges the head block into an existing page, replacing a
stale `<title>`, description or canonical rather than duplicating them.

```bash
python skills/better-seo-build/scripts/seo_build.py --root .            # plan
python skills/better-seo-build/scripts/seo_build.py --root . --write    # apply
```

### Site-wide crawl

One page is not the site. `crawl.py` discovers URLs and audits many at once:

```bash
python skills/better-seo/scripts/crawl.py https://example.com
python skills/better-seo/scripts/crawl.py https://example.com --source sitemap --limit 50
python skills/better-seo/scripts/crawl.py https://example.com --source links --depth 2
python skills/better-seo/scripts/crawl.py --fixture-dir dist/            # offline
```

Discovery order: `Sitemap:` lines in `robots.txt`, then `/sitemap.xml` (recursing
one level of sitemap-index), then same-origin links.

Deliberately timid defaults: one request at a time, `--delay 0.3`, `--limit 25`,
hard cap 200. `robots.txt` is checked before every fetch, off-origin URLs are
refused, and the limit is enforced as an error rather than a silent truncation.

Output is one JSON document:

| Field | Meaning |
|---|---|
| `score_mean` / `score_median` | report both; one broken page must not hide a healthy site |
| `score_min` / `score_max` | |
| `worst` | five lowest-scoring pages, to look at individually |
| `common_failures` | checks failing on the most pages, ranked by count then weight |
| `skipped` | URLs refused, and why (off-origin, robots, fetch failed) |
| `discovery` | which sitemaps were read and how many URLs each yielded |
| `pages` | full per-page result, same shape as a single audit |

`common_failures` is the part worth acting on first. A check failing on 31 of 50
pages is a template bug, and fixing it once is worth more than fixing any single
page.

### `/seo-audit`

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
  scripts/crawl.py             site-wide crawl + aggregate
  references/agentic-search.md AI crawler gates, answer-first structure, llms.txt
  references/onpage.md         title/description/heading/schema rules with numbers
  references/technical.md      crawl, render, canonical, CWV thresholds

skills/better-seo-build/
  SKILL.md                     the build checklist and its guardrails
  scripts/seo_build.py         framework detection + scaffolding CLI
  references/                  copied from better-seo at install time
```

`install.sh` copies `better-seo/references/` into `better-seo-build/` so the
repo keeps one source of truth while each installed skill stays self-contained.

## Develop

```bash
make check    # trigger match + audit behavior + install into a temp root
```

Tests are fixture-based, offline, stdlib only. `make check` runs `make clean`
first, so local bytecode can never ride along into an installed skill.

## License

MIT
