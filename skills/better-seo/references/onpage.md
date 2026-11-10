# On-page SEO rules

Concrete limits. When rewriting, land inside the range, not at the edge.

## Title tag

- 50-60 characters target. Google truncates around 580px, roughly 60 chars.
- Primary keyword in the first 40 characters.
- One page, one intent. Do not stuff two intents into a title.
- Brand suffix only if it costs nothing: `Primary Phrase — Brand` when the phrase is short.
- Ban: `|` chains of 4+ segments, ALL CAPS, `Best #1 Top Free`, emoji.
- Unique across the site. Duplicate titles split relevance.

Template: `<primary phrase> — <secondary benefit>` or `<primary phrase>: <specific qualifier>`.

## Meta description

- 120-155 characters. Not a ranking signal, but it is the ad copy for the click.
- Must contain the primary phrase and a concrete promise (number, timeframe, deliverable).
- No `Learn more about our services` filler. No duplicated site-wide boilerplate.
- Google rewrites it often; still write it, it is used ~60% of the time and shown in some AI answers.

## Headings

- Exactly one `<h1>`, matching the page intent, not the site name.
- H2s answer sub-questions a real user asks. H2 as a question is fine and helps extraction.
- Never skip levels for styling. Never use headings as font sizes.
- Heading text should read as a claim or a question, not `Section 1`.

## Body / extractability

- First 40-60 words after H1 answer the page's core question directly.
- One idea per paragraph, 2-4 sentences. Long unbroken blocks are not quotable.
- Use concrete numbers, dates, named entities. Vague text cannot be cited.
- Lists for steps and comparisons. Tables for specs and pricing.
- Every claim that matters gets its own sentence so a model can lift it clean.

## Internal links

- Every page reachable within 3 clicks of the homepage.
- Descriptive anchors (`audit crawl budget`, not `click here`).
- 3-10 contextual internal links per page, pointing to parent, siblings, and one deep money page.
- Orphan pages are invisible. Find them with a crawl, not by memory.

## Structured data

Minimum viable set, all via JSON-LD in the page:

| Page type | Types |
|---|---|
| Site-wide | `Organization` or `Person`, plus `WebSite` |
| Article / post | `Article` with `author`, `datePublished`, `dateModified` |
| Product | `Product` with `offers`, `aggregateRating` (only if real) |
| FAQ block | `FAQPage` |
| How-to | `HowTo` |
| Local | `LocalBusiness` with `address`, `openingHours` |

Rules:
- Markup must match visible content. Mismatch is a manual-action risk.
- `sameAs` should list real profile URLs — this is how entities get resolved.
- `dateModified` must be real, not bumped to today on every deploy.

## Canonical and duplicates

- One canonical per page, absolute URL, self-referencing on the canonical version.
- Paginated series: canonical each page to itself, do not collapse to page 1.
- Faceted/filtered URLs: `noindex, follow` or canonical to the parent, never both inconsistently.
- `www` vs non-`www`, `http` vs `https`: one 301 direction, no chains.

## Images

- Descriptive `alt`, under 125 chars, no keyword stuffing.
- Explicit `width`/`height` to prevent layout shift.
- Modern format, lazy-load below the fold, never lazy-load the LCP image.

## Anti-patterns to call out

- Keyword-stuffed titles that read like spam.
- Duplicate H1 + title on every page from a template bug.
- `noindex` left on from staging.
- Content behind an interaction with no server-rendered fallback.
- Auto-generated pages with no unique value.
- AI-generated filler paragraphs that restate the heading. Delete them.
