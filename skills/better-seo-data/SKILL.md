---
name: better-seo-data
description: >-
  Read SEO data that is not in the page HTML: Google Search Console clicks,
  impressions, CTR, average position and indexing coverage, plus Core Web Vitals
  measured by Lighthouse. Use when the user asks about traffic, impressions,
  which queries they rank for, why a page gets no clicks, how to connect Search
  Console, wants real LCP/INP/CLS numbers, or asks whether a site is slow.
  Requires credentials or a Chrome/Node toolchain; say so plainly when missing
  instead of guessing numbers.
---

# better-seo-data

Third skill in the set. Know where each job belongs:

| Question | Skill |
|---|---|
| Is this page well-formed? | `better-seo` → `audit.py` |
| Which problems are site-wide? | `better-seo` → `crawl.py` |
| Set up SEO in a project | `better-seo-build` → `seo_build.py` |
| What do users actually do in search? | **this one** → `gsc.py` |
| Is it actually slow? | **this one** → `cwv.py` |

The reason this is separate: it needs credentials and a browser toolchain. The
other two are stdlib, offline, and instant. Never move their work here.

## The rule that matters most

**No data means say no data.** If credentials are missing, report the setup steps
and stop. Never estimate traffic, never estimate position, never invent a CTR.
This skill exists to replace guesses with measurements, so guessing here would
defeat the point.

## Search Console

```bash
python <skill-dir>/scripts/gsc.py sites
python <skill-dir>/scripts/gsc.py report --property sc-domain:example.com --days 28
python <skill-dir>/scripts/gsc.py opportunities --property sc-domain:example.com
```

Exit codes carry meaning: `0` success, `2` API failure, `3` not configured. On
`3` the message contains the full setup instructions; pass them to the user.

Credentials, in order of preference:

1. `GSC_ACCESS_TOKEN` or `--token` — an OAuth access token you already have.
2. `GSC_CREDENTIALS` / `--credentials` — a JSON file with `client_id`,
   `client_secret`, `refresh_token`. The script refreshes it over plain HTTPS,
   so no crypto library is needed.

Service-account keys are **not** supported: signing an RS256 JWT needs a crypto
library outside the stdlib. Say that, rather than suggesting it will work.

### Reading the numbers honestly

| Field | Means | Does not mean |
|---|---|---|
| `clicks` | clicks from Google Search results | site visits, sessions, conversions |
| `impressions` | times a result was seen | unique people |
| `ctr` | clicks ÷ impressions, as a percentage | anything about ad performance |
| `position` | average position across queries | "we rank #3 for X" |

Data lags ~3 days; `--lag` defaults to 3 so the tail of the window is not
artificially low. Say that when reporting a partial final day.

### Opportunities: the useful output

`opportunities` lists pages with impressions above `--min-impressions` and CTR at
or below `--max-ctr`. That combination means Google already shows the page and
nobody clicks — a title and description problem, not a ranking problem. Hand
those pages to `better-seo-build` to rewrite the head tags, then re-check.

Do not report "low CTR" without naming the page and the impressions behind it.

## Core Web Vitals

```bash
python <skill-dir>/scripts/cwv.py https://example.com
python <skill-dir>/scripts/cwv.py https://example.com --mobile --json cwv.json
```

Takes 30-60 seconds and needs Chrome plus a `lighthouse` binary on PATH. Exit `3`
means the toolchain is missing; the message says how to install it. It never
installs anything itself: the `npx lighthouse@12` fallback only runs when you
pass `--allow-npx`, because that downloads a package.

Thresholds come from `references/technical.md` and are applied by the script:

| Metric | Good | Needs work | Poor |
|---|---|---|---|
| LCP | ≤ 2500 ms | ≤ 4000 ms | > 4000 ms |
| CLS | ≤ 0.1 | ≤ 0.25 | > 0.25 |
| TBT (lab proxy for INP) | ≤ 200 ms | ≤ 500 ms | > 500 ms |

**Say which kind of data it is.** Lighthouse is lab data: one synthetic run in
one browser on one machine. Real-user INP needs field data (CrUX). The script
puts this in a `caveat` field; repeat it instead of presenting lab numbers as
what users experience.

Report `failing` and the top `opportunities` by `savings_ms` — not the whole
opportunity list, and not the performance score alone.

## Reference files

Shared with the other skills at install time:

- `references/technical.md` — CWV thresholds, crawl, render.
- `references/onpage.md` — what to change when CTR is the problem.
- `references/agentic-search.md` — crawler policy and quotable structure.

## Guardrails

- Never fabricate metrics. Missing credentials or toolchain is a normal answer.
- Never present GSC `position` as a fixed ranking for a keyword.
- Never present Lighthouse lab numbers as field data.
- Never commit a credentials file, and never paste a token into a report.
- Never scrape Google to "check rankings": it breaks the terms and the results
  are not reproducible. Use GSC.
- Never install Lighthouse, Chrome or a Python package on the user's machine
  without asking first.
