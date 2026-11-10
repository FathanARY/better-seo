---
name: better-seo
description: >-
  Audit and fix a website's search visibility, both classic SEO (meta title,
  meta description, headings, canonical, structured data, crawlability) and
  agentic search / AI search visibility so pages get cited by ChatGPT,
  Perplexity, AI Overviews and Claude. Use when the user asks why their site
  does not rank, why it is not mentioned by LLMs or AI chatbots, wants an SEO
  audit, wants a content brief, robots.txt / llms.txt review, schema markup,
  internal linking plan, or asks "how do I show up in AI search".
---

# better-seo

Two jobs, one skill: make a page **findable by crawlers** and **quotable by models**.

## Order of operations

1. **Fix the scan** before touching content. A page that is not crawlable or not parseable scores zero with every engine, human or machine.
2. **Then on-page**. Title, description, H1, headings, canonical, schema.
3. **Then agentic-search surface**. Answer-first structure, extractable claims, `llms.txt`, citable entity data.
4. **Then distribution**. Internal links, sitemap, feed, `robots.txt` AI-crawler policy.

Never optimize item 3 while item 1 is broken. Report the real blocker first.

## Run the audit before advising

Do not guess a site's state. Fetch it.

The CLI ships inside this skill folder. Run it from the skill directory (the
path where this `SKILL.md` lives), not from the user's project root:

```bash
python <skill-dir>/scripts/audit.py https://example.com
python <skill-dir>/scripts/audit.py https://example.com --json out.json
python <skill-dir>/scripts/audit.py --fixture page.html    # offline, no network
python <skill-dir>/scripts/audit.py https://example.com --insecure  # TLS-intercepting proxy only
```

Copy `--json out.json` output somewhere the user can keep; do not write into the
skill directory.

Output: JSON with `url`, `score` (0-100), `checks` (each with `id`, `weight`,
`status`, `detail`), and `issues` (fail and warn lines, heaviest first). Read
`score` and every `fail` check before writing advice.

### Many pages at once

One page is not the site. When the user asks about the site as a whole, or wants
to know which problem is systemic, use the crawler in the same folder:

```bash
python <skill-dir>/scripts/crawl.py https://example.com
python <skill-dir>/scripts/crawl.py https://example.com --source sitemap --limit 50
python <skill-dir>/scripts/crawl.py https://example.com --source links --depth 2
python <skill-dir>/scripts/crawl.py --fixture-dir dist/        # offline
```

It discovers URLs from `robots.txt` `Sitemap:` directives, then `/sitemap.xml`,
then same-origin links, and audits up to `--limit` pages. Defaults are timid on
purpose: one request at a time, 0.3s apart, 25 pages, hard cap 200. It honours
`robots.txt` before fetching anything, refuses off-origin URLs, and never writes
outside the `--json` path you give it.

Report `common_failures` first. A check failing on 31 of 50 pages is a template
bug and is worth more than any single page score. `worst` is the handful to look
at individually. Give `score_median`, not just the mean, because one broken page
must not hide a healthy site.
Fix checks in descending weight order; a 12-weight fail matters more than five 4-weight fails.

If the script cannot run, fall back to manual parsing and say so explicitly.
Never present unaudited advice as audited.

## Reference files

Load only what the task needs:

- `references/agentic-search.md` — AI Overviews, ChatGPT, Perplexity citation mechanics, `llms.txt`, answer-first writing, entity grounding. Read when the user's problem is "AI does not mention us".
- `references/onpage.md` — title/description/heading/schema rules with concrete numbers and templates.
- `references/technical.md` — crawl, index, canonical, robots, sitemap, JS rendering, Core Web Vitals thresholds.

## Answer shape

Lead with the blocker and the score. Then a ranked fix list: what, why it costs
visibility, exact replacement text or markup. No generic SEO essays. If a
recommendation cannot be verified from the fetched page, mark it as unverified
instead of asserting it.

## Guardrails

- Never invent metrics, rankings, traffic, or competitor data. If the user
  supplies analytics, cite them; otherwise state the data is missing.
- Never promise a ranking or a citation.
- Never recommend cloaking, doorway pages, hidden text, link schemes, or
  `llms.txt` content that contradicts the human-facing page.
- Time-sensitive claims (AI crawler user-agents, engine behavior) are marked as
  needing a live check rather than stated as permanent fact.

## Verification before handoff

- `python <skill-dir>/scripts/audit.py --fixture <page>` exits 0 and the reported score
  moved in the intended direction after the edit.
- Every rewrite you hand over is copy-paste ready and inside the stated limits.
