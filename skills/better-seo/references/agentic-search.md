# Agentic search -- getting cited by AI answers

AI answers (Google AI Overviews / AI Mode, ChatGPT Search, Perplexity, Claude
with search, Copilot) do not rank ten links. They assemble an answer from a few
sources, sometimes only one. The goal changes from "rank in the list" to "be the
passage that gets lifted and attributed".

Two gates, in order. Fail the first and nothing else matters.

## Gate 1 -- be retrievable by the AI crawler

Check `robots.txt` for each user-agent. As of writing, and this changes, so verify:

| Engine | User-agents to check |
|---|---|
| OpenAI | `GPTBot`, `OAI-SearchBot`, `ChatGPT-User` |
| Perplexity | `PerplexityBot`, `Perplexity-User` |
| Google | `Googlebot` (AI Overviews use the normal index) |
| Anthropic | `ClaudeBot`, `Claude-User` |
| Microsoft | `bingbot` (Copilot uses Bing index) |
| Common Crawl | `CCBot` |

Rules that actually matter:

- `OAI-SearchBot` blocked means you are out of ChatGPT search. This is the single
  most common self-inflicted agentic-SEO failure.
- `CCBot` feeds training corpora, not live answers. Blocking it hurts long-term
  entity recognition, not today's citations.
- Verify the list against each vendor's own docs at audit time. Never hardcode
  this table as permanent truth in a report.
- A CDN or WAF bot-fight-mode that 403s AI user-agents is the same as a robots block,
  and is harder to notice. Test fetch with the user-agent string.

Also required:

- Server-render the body text. If the content only exists after JS execution and
  the crawler does not wait, you are invisible.
- No login wall, no cookie interstitial covering the content, no `noscript`-only text.
- `sitemap.xml` submitted and current, with real `lastmod`.

## Gate 2 -- be quotable

Crawlers fetch; models extract passages. Structure for extraction.

- **Answer first.** The first 40-60 words after the H1 state the direct answer.
  Background comes after. Inverted pyramid, not a narrative build-up.
- **Self-contained section.** Each H2 plus its paragraph should make sense lifted
  out of the page, with no "as mentioned above".
- **Claim-level sentences.** `A three-day audit costs $2,400 and covers 200 URLs.`
  A model can cite that. `Our audit is comprehensive and tailored.` it cannot.
- **Named entities, dates, numbers.** Who, when, how much, how many.
- **Tables for comparison.** Models lift tables well; they lift a pricing grid
  better than three paragraphs describing the grid.
- **Question-shaped headings.** Matches query form. `How long does an SEO audit take?`
- **Definitions.** `X is <one-sentence definition>` near first mention. This is the
  highest-citation pattern for "what is" queries.
- **Citable entity data.** Consistent name, description, logo, `sameAs` links to
  real profiles. Entity ambiguity is why a competitor gets cited for your name.

## llms.txt

A proposed convention: a markdown file at `/llms.txt` giving an LLM a curated map
of the site. Optional, not standardized, no engine has guaranteed support.

Ship it only if it is genuinely useful:

```
# Site Name

> One-sentence description of what this site is and who it is for.

## Core pages
- [Pricing](https://example.com/pricing): what it costs, plan tiers
- [Docs](https://example.com/docs): full API reference

## Articles
- [How to do X](https://example.com/x): step-by-step, updated 2026-03
```

Rules: link only real, canonical, publicly accessible URLs. Never use it to
smuggle content hidden from users. Never present it as a ranking factor. If the
user asks "will this get me cited", answer: unproven, cheap to ship, keep
maintaining the HTML.

## What does not work

- Keyword stuffing for AI. Extraction rewards specificity, not repetition.
- Hidden text aimed at models. Same spam risk as cloaking.
- Fake FAQ schema with questions no user asked.
- `llms.txt` with hundreds of auto-generated lines nobody reviewed.
- Publishing the same article at five URLs to "cover more queries". Consolidate.

## Verification at audit time

Do not assert engine behavior from memory. At audit time:

1. Fetch `robots.txt` and read the live user-agent rules.
2. Fetch the page as the target user-agent and confirm the body text is present
   without JS.
3. Resolve the vendor docs for the current crawler list before publishing a table.
4. Recommend re-checking quarterly, and label the date of the last check.
