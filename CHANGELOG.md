# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semver](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-11-11

### Fixed

- **The AI-crawler gate no longer reports the opposite of reality.** It used
  `urllib.robotparser`, which reads `*` and `$` as literal characters and ignores
  `Allow:` entirely, so `Disallow: /*` came back as "allow everything". Replaced
  with an RFC 9309 matcher: longest match wins, `Allow` wins a tie, wildcards and
  `$` anchors honoured, user-agent specificity respected. A robots.txt that
  returns 401/403 is now treated as disallow-all, as the RFC requires.
- `X-Robots-Tag` response headers are read. A `noindex` sent only as a header used
  to be invisible to the audit.
- Canonical and links are read as parsed attributes instead of raw substrings. A
  commented-out canonical used to pass; a valid unquoted one failed.
- `noscript`, `nav`, `header` and `footer` no longer count as page content, so a
  client-rendered shell is not credited with an `<h1>` an AI crawler never sees.
- JSON-LD is excluded from the word count and must carry an `@type`; `{}` is not
  structured data.
- Internal links compare origins instead of substring-matching the host, so
  `notexample.com` is not counted as an internal link on `example.com`.
- Title and description thresholds now match `references/onpage.md` (title 50-60,
  description 120-155) instead of contradicting it.
- A page with `noindex` scores 0, which `SKILL.md` already promised.

### Added

- `ai_crawler_access` check: fetches the audited URL as `GPTBot`,
  `OAI-SearchBot`, `PerplexityBot` and `ClaudeBot`. A WAF or bot-fight rule that
  403s AI user-agents is a robots block in effect and was previously invisible.
- `heading_levels` check: flags skipped outline levels.
- `make check-live`: audits a real page and asserts the checks the README
  advertises still exist.
- Regression tests for every fix above.

### Changed

- `crawl.py` applies robots.txt before fetching during link discovery, and reuses
  the bodies and headers it already downloaded. Four pages cost 15 requests
  instead of 25.
- README leads with the install command and states that no API keys or
  dependencies are needed.
- Version bumped across all seven manifests.

## [0.1.0] - 2026-11-10

### Added

- Initial release: `better-seo`, `better-seo-build`, `better-seo-data`, the
  audit and crawl CLIs, three reference files, and slash commands.
