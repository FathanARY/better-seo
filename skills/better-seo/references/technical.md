# Technical SEO rules

## Crawl and index

- `robots.txt` at the root, plain text, `User-agent` blocks, `Disallow` paths
  only. Never disallow CSS/JS the renderer needs.
- Use `noindex` for exclusion, not `Disallow`. Disallowed pages still get indexed
  by URL if linked.
- `sitemap.xml`: absolute URLs, under 50k entries per file, `lastmod` real.
  Reference it from `robots.txt`.
- Return correct status codes: 200 for live, 301 for permanent moves, 410 for
  gone, 404 for never existed. Soft 404s (`200` with "not found" body) confuse
  every crawler.
- No redirect chains. One hop. Fix `http -> https -> www` double redirects.

## Rendering

- Prefer server-side rendering or static generation for anything indexable.
- Client-side only content is a bet that the crawler executes your JS and waits.
  Google mostly does, with delays. Most AI crawlers do not run JS at all.
- Keep the rendered DOM close to the server HTML. Mismatch means whatever the
  crawler sees is what you get ranked on.
- Check with `curl` and with a JS-off fetch. If text disappears, it is at risk.

## Canonical and URL structure

- Absolute, self-referencing canonical on every page.
- Lowercase, hyphen-separated, no parameters for content identity.
- One URL per piece of content. Trailing slash: pick one, 301 the other.
- Query parameters that change content (sort, filter, page) must either be
  `noindex, follow` or canonical to a stable parent.
- Keep URL depth shallow: `/category/page` beats `/a/b/c/d/page`.

## Performance thresholds (Core Web Vitals, field data)

| Metric | Good | Needs work | Poor |
|---|---|---|---|
| LCP | <= 2.5s | 2.5-4.0s | > 4.0s |
| INP | <= 200ms | 200-500ms | > 500ms |
| CLS | <= 0.1 | 0.1-0.25 | > 0.25 |

Fixes, in order of payoff:

1. LCP: serve the hero image in modern format at the right size, preload it, no
   lazy-load on it, avoid render-blocking CSS before it.
2. INP: split long tasks, defer non-critical JS, cut third-party scripts. Third-party
   tags are usually the whole problem.
3. CLS: explicit dimensions on media, reserve space for ads/embeds, no font swap
   without `size-adjust` or `font-display` care.

## Structured data validation

- JSON-LD, valid JSON, no trailing commas, no HTML inside string values.
- `@context` present, `@type` matches visible content.
- Test with a schema validator before shipping. A broken block is worse than none
  only if it lies; an empty block is just noise.
- `BreadcrumbList` mirrors visible breadcrumbs, not invented hierarchy.

## Internationalization, if applicable

- `hreflang` pairs must be reciprocal, including `x-default`.
- `lang` attribute on `<html>` matching the page language.
- Do not machine-translate without review; thin translations get ignored or penalized.

## Security and trust signals that affect visibility

- HTTPS everywhere, valid cert, no mixed content.
- No malware/interstitial flags. Check Search Console security issues, not vibes.
- Visible contact and ownership signals for YMYL topics.

## Monitoring, not guessing

- Verify with Search Console and Bing Webmaster Tools. Sitemap status, coverage
  exclusions, and manual actions come from there, not from a third-party guess.
- Log-file analysis for real crawl behavior when indexation is disputed.
- Check AI crawler hits in server logs by user-agent; that is the only direct
  evidence an AI engine visited.
