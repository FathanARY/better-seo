#!/usr/bin/env python3
"""SEO + agentic-search audit. Stdlib only.

Usage:
    python scripts/audit.py https://example.com
    python scripts/audit.py https://example.com --json out.json
    python scripts/audit.py --fixture page.html
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; better-seo-audit/1.0)"

SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


class Page(HTMLParser):
    """Collects the handful of facts the checks need."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.lang = ""
        self.meta: dict[str, str] = {}
        self.headings: list[tuple[int, str]] = []
        self.links: list[str] = []
        self.imgs: list[tuple[str, str]] = []
        self.ld_blocks: list[str] = []
        self.paras: list[str] = []
        self.text: list[str] = []
        self._skip = 0
        self._buf: list[str] = []
        self._kind = ""
        self._level = 0
        self._in_ld = False

    # -- helpers ---------------------------------------------------------
    def _flush(self) -> None:
        body = " ".join("".join(self._buf).split())
        kind, self._kind, self._buf = self._kind, "", []
        if not body:
            return
        if kind == "title":
            self.title = body
        elif kind == "ld":
            self.ld_blocks.append(body)
        elif kind == "p":
            self.paras.append(body)
        elif kind.startswith("h"):
            self.headings.append((self._level, body))

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self._flush()
            self._kind = "title"
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")
        elif tag in HEADINGS:
            self._flush()
            self._kind = tag
            self._level = int(tag[1])
        elif tag == "a":
            href = a.get("href", "").strip()
            if href:
                self.links.append(href)
        elif tag == "img":
            self.imgs.append((a.get("src", ""), a.get("alt", "")))
        elif tag == "script":
            typ = a.get("type", "").lower()
            if "ld+json" in typ:
                self._flush()
                self._kind = "ld"
                self._in_ld = True
            else:
                self._skip += 1
        elif tag == "p":
            self._flush()
            self._kind = "p"
        elif tag in SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("title", "p") or tag in HEADINGS:
            self._flush()
        elif tag == "script":
            if self._in_ld:
                self._flush()
                self._in_ld = False
            elif self._skip:
                self._skip -= 1
        elif tag in SKIP_TAGS and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if self._kind:
            self._buf.append(data)
        if not self._skip:
            self.text.append(data)


def parse_html(html: str) -> Page:
    p = Page()
    p.feed(html)
    p.close()
    p._flush()
    return p


def fetch(url: str, timeout: float = 15.0, insecure: bool = False) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, "replace")


def fetch_optional(url: str, insecure: bool = False) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        ctx = ssl._create_unverified_context() if insecure else None
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, OSError, ValueError):
        return 0, ""


def check(cid, weight, status, detail):
    return {"id": cid, "weight": weight, "status": status, "detail": detail}


def audit(page: Page, html: str, url: str | None, insecure: bool = False) -> dict:
    out: list[dict] = []
    m = page.meta

    def add(cid, weight, status, detail):
        out.append(check(cid, weight, status, detail))

    # indexability first -- a blocked page scores zero regardless of the rest
    robots = (m.get("robots") or "").lower()
    if "noindex" in robots or "none" in robots:
        add("indexable", 12, "fail", f'meta robots="{m.get("robots")}" blocks indexing')
    else:
        add("indexable", 12, "pass", 'no noindex directive in meta robots')

    t = page.title
    if not t:
        add("title", 12, "fail", "no <title>")
    elif len(t) < 30:
        add("title", 12, "warn", f"title {len(t)} chars, under 30: {t!r}")
    elif len(t) > 65:
        add("title", 12, "warn", f"title {len(t)} chars, truncation risk: {t!r}")
    else:
        add("title", 12, "pass", f"title {len(t)} chars")

    d = m.get("description", "")
    if not d:
        add("meta_description", 10, "fail", "no meta description")
    elif not (70 <= len(d) <= 160):
        add("meta_description", 10, "warn", f"description {len(d)} chars, target 70-160")
    else:
        add("meta_description", 10, "pass", f"description {len(d)} chars")

    h1s = [x for lvl, x in page.headings if lvl == 1]
    if not h1s:
        add("h1_single", 10, "fail", "no <h1>")
    elif len(h1s) > 1:
        add("h1_single", 10, "warn", f"{len(h1s)} <h1> elements: {h1s[:3]}")
    else:
        add("h1_single", 10, "pass", f"single h1: {h1s[0][:70]!r}")

    # canonical is only observable on a rendered page, so look for it in the raw html
    if 'rel="canonical"' in html or "rel='canonical'" in html:
        add("canonical", 8, "pass", "rel=canonical present")
    else:
        add("canonical", 8, "warn", "no rel=canonical link")

    blocks = 0
    bad = 0
    for b in page.ld_blocks:
        try:
            json.loads(b)
            blocks += 1
        except json.JSONDecodeError:
            bad += 1
    if bad:
        add("structured_data", 9, "fail", f"{bad} JSON-LD block(s) fail to parse")
    elif blocks:
        add("structured_data", 9, "pass", f"{blocks} valid JSON-LD block(s)")
    else:
        add("structured_data", 9, "warn", "no JSON-LD structured data")

    add("lang", 4, "pass" if page.lang else "warn",
        f'<html lang="{page.lang}">' if page.lang else "no lang attribute on <html>")

    add("viewport", 4, "pass" if "viewport" in m else "warn",
        "viewport meta present" if "viewport" in m else "no viewport meta")

    words = len(" ".join(page.text).split())
    if words >= 300:
        add("word_count", 8, "pass", f"{words} words")
    elif words >= 120:
        add("word_count", 8, "warn", f"{words} words, thin for extraction")
    else:
        add("word_count", 8, "fail", f"{words} words, too thin to be quotable")

    lead = page.paras[0] if page.paras else ""
    if 80 <= len(lead) <= 600:
        add("answer_first", 7, "pass", f"opening paragraph {len(lead)} chars")
    elif lead:
        add("answer_first", 7, "warn", f"opening paragraph {len(lead)} chars, aim 80-600")
    else:
        add("answer_first", 7, "fail", "no opening paragraph after the heading")

    h2s = [x for lvl, x in page.headings if lvl == 2]
    if len(h2s) >= 2:
        add("heading_structure", 6, "pass", f"{len(h2s)} h2 sections")
    elif h2s:
        add("heading_structure", 6, "warn", "only 1 h2 section")
    else:
        add("heading_structure", 6, "fail", "no h2 sections")

    qs = [h for h in h2s if h.rstrip().endswith("?")]
    add("question_headings", 4, "pass" if qs else "warn",
        f"{len(qs)} question-shaped h2" if qs else "no question-shaped h2 headings")

    if page.imgs:
        missing = [s for s, alt in page.imgs if not alt.strip()]
        status = "pass" if not missing else ("warn" if len(missing) < len(page.imgs) else "fail")
        add("images_alt", 6, status,
            f"{len(missing)}/{len(page.imgs)} images lack alt text")
    else:
        add("images_alt", 6, "pass", "no images on page")

    internal = [h for h in page.links if h.startswith(("/", "#"))]
    if url:
        host = urllib.parse.urlparse(url).netloc
        internal = [h for h in page.links
                    if h.startswith(("/", "#")) or host in h]
    if len(internal) >= 3:
        add("internal_links", 6, "pass", f"{len(internal)} internal links")
    elif internal:
        add("internal_links", 6, "warn", f"{len(internal)} internal links, aim 3+")
    else:
        add("internal_links", 6, "fail", "no internal links")

    has_list = "<ul" in html or "<ol" in html or "<table" in html
    add("lists_tables", 4, "pass" if has_list else "warn",
        "list or table markup present" if has_list else "no list/table, extraction is harder")

    social = m.get("og:title") or m.get("twitter:title")
    add("social_meta", 4, "pass" if social else "warn",
        "Open Graph title present" if social else "no og:title / twitter:title")

    # network-only checks, skipped for offline fixtures
    if url:
        base = f"{urllib.parse.urlparse(url).scheme}://{urllib.parse.urlparse(url).netloc}"
        code, body = fetch_optional(base + "/robots.txt", insecure)
        if code == 200 and body.strip():
            blocked = [ua for ua in ("GPTBot", "OAI-SearchBot", "PerplexityBot", "ClaudeBot")
                       if ua in body]
            add("robots_txt", 6, "pass", f"robots.txt found, mentions: {blocked or 'no AI agents'}")
        else:
            add("robots_txt", 6, "warn", f"robots.txt status {code}")

        code, body = fetch_optional(base + "/llms.txt", insecure)
        add("llms_txt", 3, "pass" if code == 200 and body.strip() else "warn",
            f"llms.txt status {code}" if code != 200 else "llms.txt present")
    else:
        add("robots_txt", 6, "skip", "offline fixture: robots.txt not fetchable")
        add("llms_txt", 3, "skip", "offline fixture: llms.txt not fetchable")

    scored = [c for c in out if c["status"] != "skip"]
    total = sum(c["weight"] for c in scored) or 1
    earned = sum(c["weight"] for c in scored if c["status"] == "pass")
    earned += sum(c["weight"] * 0.5 for c in scored if c["status"] == "warn")
    score = round(earned / total * 100)

    issues = [f'{c["id"]}: {c["detail"]}' for c in out if c["status"] in ("fail", "warn")]
    issues.sort(key=lambda s: -next(c["weight"] for c in out if c["id"] == s.split(":")[0]))
    return {"url": url or "fixture", "score": score, "checks": out, "issues": issues}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Audit a page for SEO and agentic-search visibility.")
    ap.add_argument("url", nargs="?", help="URL to audit")
    ap.add_argument("--fixture", help="local HTML file, no network")
    ap.add_argument("--json", help="write JSON to this path")
    ap.add_argument("--quiet", action="store_true", help="suppress the human summary")
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification (corporate MITM proxies only)")
    args = ap.parse_args(argv)

    if not args.url and not args.fixture:
        ap.error("give a URL or --fixture")

    if args.fixture:
        with open(args.fixture, encoding="utf-8", errors="replace") as f:
            html, url = f.read(), None
    else:
        try:
            html, url = fetch(args.url, insecure=args.insecure), args.url
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(json.dumps({"error": str(e), "url": args.url}), file=sys.stderr)
            return 2

    result = audit(parse_html(html), html, url, args.insecure)
    blob = json.dumps(result, indent=2, ensure_ascii=False)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            f.write(blob)
    if not args.quiet:
        print(blob)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
