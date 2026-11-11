#!/usr/bin/env python3
"""SEO + agentic-search audit. Stdlib only.

Lives inside the skill folder; run it by path.

Usage:
    python <skill-dir>/scripts/audit.py https://example.com
    python <skill-dir>/scripts/audit.py https://example.com --json out.json
    python <skill-dir>/scripts/audit.py --fixture page.html
    python <skill-dir>/scripts/audit.py URL --insecure   # TLS-intercepting proxy only
    python <skill-dir>/scripts/audit.py URL --no-crawler-probe

Exit 0 on a completed audit, 2 when the fetch fails.
"""
from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; better-seo-audit/1.0)"

SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}
REGION_TAGS = {"nav", "aside", "header", "footer", "form"}
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
        self.canonicals: list[str] = []
        self.imgs: list[tuple[str, str]] = []
        self.ld_blocks: list[str] = []
        self.paras: list[str] = []
        self.text: list[str] = []
        self.after_h1 = False
        self._skip = 0
        self._region = 0
        self._buf: list[str] = []
        self._kind = ""
        self._level = 0
        self._in_ld = False

    # -- helpers ---------------------------------------------------------
    def _flush(self) -> None:
        body = " ".join("".join(self._buf).split())
        kind, self._kind, self._buf = self._kind, "", []
        if not body or self._skip:
            return
        if kind == "title":
            self.title = body
        elif kind == "ld":
            self.ld_blocks.append(body)
        elif kind == "p":
            if self.after_h1 and not self._region:
                self.paras.append(body)
        elif kind.startswith("h"):
            self.headings.append((self._level, body))

    # -- parser hooks ----------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in SKIP_TAGS and tag not in ("script",):
            self._skip += 1
        elif tag in HEADINGS:
            self._flush()
            self._kind = tag
            self._level = int(tag[1])
            if tag == "h1":
                self.after_h1 = True
        elif tag in REGION_TAGS and not self._skip:
            self._region += 1
        elif tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self._flush()
            self._kind = "title"
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or a.get("http-equiv") or "").lower()
            if key:
                self.meta[key] = a.get("content", "")
        elif tag == "a":
            href = a.get("href", "").strip()
            if href:
                self.links.append(href)
        elif tag == "link":
            rel = a.get("rel", "").lower().split()
            href = a.get("href", "").strip()
            if "canonical" in rel and href:
                self.canonicals.append(href)
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
            if not self._skip:
                self._flush()
                self._kind = "p"

    def handle_endtag(self, tag):
        if tag in ("title", "p") or tag in HEADINGS:
            self._flush()
        elif tag == "script":
            if self._in_ld:
                self._flush()
                self._in_ld = False
            elif self._skip:
                self._skip -= 1
        elif tag in SKIP_TAGS:
            if self._skip:
                self._skip -= 1
        elif tag in REGION_TAGS and self._region:
            self._region -= 1

    def handle_data(self, data):
        if self._kind:
            self._buf.append(data)
        # JSON-LD is machine metadata, not page copy: keep it out of the word count.
        if not self._skip and not self._in_ld and not self._region:
            self.text.append(data)

def parse_html(html: str) -> Page:
    p = Page()
    p.feed(html)
    p.close()
    p._flush()
    return p

# Some CDNs answer 406 when Accept is missing or too narrow.
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en;q=0.9,*;q=0.5",
}

def _open(url: str, timeout: float, insecure: bool, ua: str | None = None):
    req = urllib.request.Request(url, headers={**HEADERS, **({"User-Agent": ua} if ua else {})})
    ctx = ssl._create_unverified_context() if insecure else None
    return urllib.request.urlopen(req, timeout=timeout, context=ctx)

def fetch_page(url: str, timeout: float = 20.0, insecure: bool = False) -> tuple[str, dict]:
    """Body plus the response headers, so X-Robots-Tag is not invisible."""
    with _open(url, timeout, insecure) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, "replace"), dict(r.headers)

def fetch(url: str, timeout: float = 20.0, insecure: bool = False) -> str:
    return fetch_page(url, timeout, insecure)[0]

# Optional side files (robots, llms) are fetched once per run, not once per page:
# the crawler audits up to 200 pages on one origin.
_OPTIONAL_CACHE: dict[tuple[str, bool], tuple[int, str]] = {}

def fetch_optional(url: str, insecure: bool = False) -> tuple[int, str]:
    key = (url, insecure)
    if key in _OPTIONAL_CACHE:
        return _OPTIONAL_CACHE[key]
    try:
        with _open(url, 10.0, insecure) as r:
            out = (r.status, r.read(500_000).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        out = (e.code, "")
    except (urllib.error.URLError, OSError, ValueError):
        out = (0, "")
    _OPTIONAL_CACHE[key] = out
    return out

AI_CRAWLERS = ("GPTBot", "OAI-SearchBot", "PerplexityBot", "ClaudeBot")

class RobotsRules:
    """RFC 9309 matching, which urllib.robotparser does not implement.

    robotparser ignores `Allow:` entirely and treats `*` and `$` as literal
    characters, so `Disallow: /*` reads as "allow everything". Both mistakes
    invert the answer on real sites, so the gate is evaluated here instead.
    """

    def __init__(self, body: str = "") -> None:
        self.html = body.lstrip().lower().startswith(("<", "<!doctype"))
        self.groups: list[dict] = []
        cur: dict | None = None
        for raw in (body or "").splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key, val = key.strip().lower(), val.strip()
            if key == "user-agent":
                if cur is None or cur["rules"]:
                    cur = {"agents": [], "rules": []}
                    self.groups.append(cur)
                cur["agents"].append(val.lower())
            elif key in ("allow", "disallow"):
                if cur is None:
                    cur = {"agents": ["*"], "rules": []}
                    self.groups.append(cur)
                if val:
                    cur["rules"].append((key == "allow", val))

    @staticmethod
    def _hit(pattern: str, path: str) -> bool:
        anchored = pattern.endswith("$")
        pat = pattern[:-1] if anchored else pattern
        rx = ".*".join(re.escape(part) for part in pat.split("*"))
        return re.fullmatch(rx, path) is not None if anchored else re.match(rx, path) is not None

    def _rules_for(self, ua: str) -> list[tuple[bool, str]]:
        ua = ua.lower()
        named = [g for g in self.groups if any(a != "*" and a in ua for a in g["agents"])]
        if named:
            return [r for g in named for r in g["rules"]]
        return [r for g in self.groups if "*" in g["agents"] for r in g["rules"]]

    def can_fetch(self, ua: str, url: str) -> bool:
        p = urllib.parse.urlparse(url)
        path = p.path or "/"
        if p.query:
            path += "?" + p.query
        rules = self._rules_for(ua)
        if not rules:
            return True
        best_len, best_allow = -1, True
        for allow, pattern in rules:
            if pattern == "/" or self._hit(pattern, path):
                n = len(pattern)
                if n > best_len or (n == best_len and allow):
                    best_len, best_allow = n, allow
        return best_allow

def evaluate_robots(body: str, page_url: str) -> tuple[str, str]:
    """Judge robots.txt by what it actually permits, not by the file existing."""
    rules = RobotsRules(body)
    if rules.html:
        return "warn", "robots.txt serves an HTML page, no rules usable"
    blocked = [ua for ua in AI_CRAWLERS if not rules.can_fetch(ua, page_url)]
    if blocked:
        return "fail", f"robots.txt blocks AI crawlers on this URL: {', '.join(blocked)}"
    named = [ua for ua in AI_CRAWLERS if ua.lower() in body.lower()]
    if named:
        return "pass", f"AI crawlers allowed: {', '.join(named)}"
    return "pass", "no AI-crawler rules; default allow-all applies"

def crawler_probe(url: str, insecure: bool = False) -> tuple[str, str]:
    """Fetch the audited URL as each AI crawler. A WAF 403 is a robots block in effect."""
    denied, errors = [], []
    for bot in AI_CRAWLERS:
        try:
            with _open(url, 15.0, insecure, ua=f"{bot}/1.0") as r:
                if r.status >= 400:
                    denied.append(bot)
        except urllib.error.HTTPError as e:
            (denied if e.code >= 400 else errors).append(bot)
        except (urllib.error.URLError, OSError, ValueError):
            errors.append(bot)
    if denied:
        return "fail", f"URL refuses AI crawler user-agents: {', '.join(denied)}"
    if errors:
        return "warn", f"crawler probe inconclusive for: {', '.join(errors)}"
    return "pass", f"all {len(AI_CRAWLERS)} AI crawlers received 2xx"

def check(cid, weight, status, detail):
    return {"id": cid, "weight": weight, "status": status, "detail": detail}

def _internal(href: str, url: str | None) -> bool:
    if href.startswith("#") or href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return False
    if url is None:
        return href.startswith(("/", "./", "../")) or "://" not in href
    target = urllib.parse.urlparse(urllib.parse.urljoin(url, href))
    here = urllib.parse.urlparse(url)
    return (target.scheme, target.netloc.lower()) == (here.scheme, here.netloc.lower())

def _same_url(a: str, b: str) -> bool:
    pa, pb = urllib.parse.urlparse(a), urllib.parse.urlparse(b)
    norm = lambda p: (p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/") or "/")
    return norm(pa) == norm(pb)

def audit(page: Page, html: str, url: str | None, insecure: bool = False,
          headers: dict | None = None, crawler_check: bool = False,
          crawler_result: tuple[str, str] | None = None) -> dict:
    out: list[dict] = []
    m = page.meta
    hdrs = {k.lower(): v for k, v in (headers or {}).items()}

    def add(cid, weight, status, detail):
        out.append(check(cid, weight, status, detail))

    # indexability first -- a blocked page scores zero regardless of the rest
    tokens = {t.strip() for t in (m.get("robots") or "").lower().replace(",", " ").split()}
    header_robots = (hdrs.get("x-robots-tag") or "").lower()
    if "noindex" in tokens or "none" in tokens:
        add("indexable", 12, "fail", f'meta robots="{m.get("robots")}" blocks indexing')
    elif "noindex" in header_robots:
        add("indexable", 12, "fail", f"X-Robots-Tag header blocks indexing: {header_robots}")
    else:
        add("indexable", 12, "pass", "no noindex directive in meta robots or X-Robots-Tag")

    t = page.title
    if not t:
        add("title", 12, "fail", "no <title>")
    elif len(t) < 30:
        add("title", 12, "warn", f"title {len(t)} chars, under the 30 char floor: {t!r}")
    elif not 50 <= len(t) <= 60:
        add("title", 12, "warn", f"title {len(t)} chars, outside the 50-60 target: {t!r}")
    else:
        add("title", 12, "pass", f"title {len(t)} chars")

    d = m.get("description", "")
    if not d:
        add("meta_description", 10, "fail", "no meta description")
    elif not d.strip():
        add("meta_description", 10, "fail", "empty meta description")
    elif not 120 <= len(d) <= 155:
        add("meta_description", 10, "warn",
            f"description {len(d)} chars, outside the 120-155 target")
    else:
        add("meta_description", 10, "pass", f"description {len(d)} chars")

    h1s = [x for lvl, x in page.headings if lvl == 1]
    if not h1s:
        add("h1_single", 10, "fail", "no <h1>")
    elif len(h1s) > 1:
        add("h1_single", 10, "warn", f"{len(h1s)} <h1> elements: {h1s[:3]}")
    else:
        add("h1_single", 10, "pass", f"single h1: {h1s[0][:70]!r}")

    canon = page.canonicals
    if not canon:
        add("canonical", 8, "warn", "no rel=canonical link")
    elif len(canon) > 1:
        add("canonical", 8, "warn", f"{len(canon)} rel=canonical links: {canon[:3]}")
    elif not urllib.parse.urlparse(canon[0]).netloc:
        add("canonical", 8, "warn", f"canonical is relative, must be absolute: {canon[0]!r}")
    elif url and not _same_url(canon[0], url):
        add("canonical", 8, "pass",
            f"canonical consolidates to another URL: {canon[0]} (confirm that is intended)")
    else:
        add("canonical", 8, "pass", f"self-referencing canonical: {canon[0]}")

    blocks = 0
    bad = 0
    empty = 0
    for b in page.ld_blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError:
            bad += 1
            continue

        def has_type(node) -> bool:
            if isinstance(node, dict):
                return "@type" in node or any(has_type(v) for v in node.values())
            if isinstance(node, list):
                return any(has_type(v) for v in node)
            return False

        if not has_type(data):
            empty += 1
        else:
            blocks += 1
    if bad:
        add("structured_data", 9, "fail", f"{bad} JSON-LD block(s) fail to parse")
    elif empty:
        add("structured_data", 9, "fail", f"{empty} JSON-LD block(s) carry no @type")
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
        add("answer_first", 7, "pass", f"opening paragraph after h1 is {len(lead)} chars")
    elif lead:
        add("answer_first", 7, "warn", f"opening paragraph {len(lead)} chars, aim 80-600")
    elif h1s:
        add("answer_first", 7, "fail", "no paragraph after the h1: answer is not stated first")
    else:
        add("answer_first", 7, "fail", "no h1 and no opening paragraph to extract")

    h2s = [x for lvl, x in page.headings if lvl == 2]
    skips = [b for a, b in zip(page.headings, page.headings[1:]) if b[0] - a[0] > 1]
    if len(h2s) >= 2:
        add("heading_structure", 6, "pass", f"{len(h2s)} h2 sections")
    elif h2s:
        add("heading_structure", 6, "warn", "only 1 h2 section")
    else:
        add("heading_structure", 6, "fail", "no h2 sections")

    qs = [h for h in h2s if h.rstrip().endswith("?")]
    add("question_headings", 4, "pass" if qs else "warn",
        f"{len(qs)} question-shaped h2" if qs else "no question-shaped h2 headings")

    if skips:
        add("heading_levels", 4, "warn",
            f"heading level skipped: {skips[:2]} (breaks outline)")
    else:
        add("heading_levels", 4, "pass", "no skipped heading levels")

    if page.imgs:
        missing = [s for s, alt in page.imgs if not alt.strip()]
        status = "pass" if not missing else ("warn" if len(missing) < len(page.imgs) else "fail")
        add("images_alt", 6, status,
            f"{len(missing)}/{len(page.imgs)} images lack alt text")
    else:
        add("images_alt", 6, "pass", "no images on page")

    internal = [h for h in page.links if _internal(h, url)]
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
        if code == 200:
            add("robots_txt", 6, *evaluate_robots(body, url))
        elif code in (401, 403):
            add("robots_txt", 6, "fail",
                f"robots.txt status {code}: RFC 9309 says treat as disallow-all")
        elif code == 0:
            add("robots_txt", 6, "warn", "robots.txt unreachable, allow-all assumed")
        else:
            add("robots_txt", 6, "warn",
                f"robots.txt status {code}, allow-all assumed (no rules to read)")

        code, body = fetch_optional(base + "/llms.txt", insecure)
        if code == 200 and body.strip() and not body.lstrip().lower().startswith(("<", "<!doctype")):
            add("llms_txt", 3, "pass", "llms.txt present and not HTML")
        elif code == 200:
            add("llms_txt", 3, "warn", "llms.txt returns HTML, not the markdown convention")
        else:
            add("llms_txt", 3, "warn", f"llms.txt status {code}")

        if crawler_result is not None:
            add("ai_crawler_access", 10, *crawler_result)
        elif crawler_check:
            add("ai_crawler_access", 10, *crawler_probe(url, insecure))
        else:
            add("ai_crawler_access", 10, "skip", "crawler probe not requested")
    else:
        add("robots_txt", 6, "skip", "offline fixture: robots.txt not fetchable")
        add("llms_txt", 3, "skip", "offline fixture: llms.txt not fetchable")
        add("ai_crawler_access", 10, "skip", "offline fixture: crawler probe not possible")

    scored = [c for c in out if c["status"] != "skip"]
    total = sum(c["weight"] for c in scored) or 1
    earned = sum(c["weight"] for c in scored if c["status"] == "pass")
    earned += sum(c["weight"] * 0.5 for c in scored if c["status"] == "warn")
    score = round(earned / total * 100)

    # Documented order of operations: a page crawlers cannot index scores zero.
    if any(c["id"] == "indexable" and c["status"] == "fail" for c in out):
        score = 0

    issues = [f'{c["id"]}: {c["detail"]}' for c in out if c["status"] in ("fail", "warn")]
    weight_of = {}
    for c in out:
        weight_of[c["id"]] = c["weight"]
    issues.sort(key=lambda s: -weight_of[s.split(":")[0]])
    return {"url": url or "fixture", "score": score, "checks": out, "issues": issues}

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Audit a page for SEO and agentic-search visibility.")
    ap.add_argument("url", nargs="?", help="URL to audit")
    ap.add_argument("--fixture", help="local HTML file, no network")
    ap.add_argument("--json", help="write JSON to this path")
    ap.add_argument("--quiet", action="store_true", help="suppress the human summary")
    ap.add_argument("--no-crawler-probe", action="store_true",
                    help="skip the 4 requests that test AI user-agents")
    ap.add_argument("--insecure", action="store_true",
                    help="skip TLS verification (corporate MITM proxies only)")
    args = ap.parse_args(argv)

    if not args.url and not args.fixture:
        ap.error("give a URL or --fixture")

    headers: dict = {}
    if args.fixture:
        with open(args.fixture, encoding="utf-8", errors="replace") as f:
            html, url = f.read(), None
    else:
        try:
            html, headers = fetch_page(args.url, insecure=args.insecure)
            url = args.url
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(json.dumps({"error": str(e), "url": args.url}), file=sys.stderr)
            return 2

    result = audit(parse_html(html), html, url, args.insecure, headers,
                   crawler_check=bool(url) and not args.no_crawler_probe)
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
