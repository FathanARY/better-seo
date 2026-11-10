#!/usr/bin/env python3
"""Audit many pages of one site: discover URLs, audit each, aggregate. Stdlib only.

Lives inside the better-seo skill; run it by path.

Usage:
    python <skill-dir>/scripts/crawl.py https://example.com
    python <skill-dir>/scripts/crawl.py https://example.com --source sitemap
    python <skill-dir>/scripts/crawl.py https://example.com --source links --depth 2
    python <skill-dir>/scripts/crawl.py --fixture-dir tests/fixtures/site

Defaults are deliberately timid: one request at a time, 0.3s apart, 25 pages.
A crawl that hammers a server is indistinguishable from an attack.

Output: one JSON document on stdout (or --json PATH) with per-page results, a
site aggregate, and the failures ranked by how many pages share them.

Exit 0 when at least one page was audited, 2 when nothing could be fetched,
3 when the URL budget was refused (limit above the hard cap).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit as audit_mod  # noqa: E402

DEFAULT_LIMIT = 25
HARD_LIMIT = 200
DEFAULT_DELAY = 0.3
MAX_SITEMAP_DEPTH = 2
SITEMAP_CANDIDATES = ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml")
NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


def same_origin(url: str, origin: tuple[str, str]) -> bool:
    p = urllib.parse.urlparse(url)
    return (p.scheme, p.netloc.lower()) == origin


def normalise(base: str, href: str) -> str | None:
    """Absolute, fragment-free http(s) URL, or None when it is not crawlable."""
    href = (href or "").strip()
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None
    absolute = urllib.parse.urljoin(base, href)
    p = urllib.parse.urlparse(absolute)
    if p.scheme not in ("http", "https") or not p.netloc:
        return None
    return urllib.parse.urlunparse(p._replace(fragment=""))


def dedupe(urls: list[str]) -> list[str]:
    """Drop duplicates and the same path reachable with and without a slash."""
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        key = u.rstrip("/") or u
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


# --- discovery -------------------------------------------------------------

def parse_sitemap(body: str) -> tuple[list[str], list[str]]:
    """Return (page urls, nested sitemap urls). Tolerates a namespace-less file."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return [], []

    def locs(entry_tag: str) -> list[str]:
        """<loc> lives INSIDE each <url> or <sitemap> entry, never beside it."""
        out = []
        for entry in root.iter():
            if entry.tag.replace(NS, "") != entry_tag:
                continue
            for child in entry:
                if child.tag.replace(NS, "") == "loc" and (child.text or "").strip():
                    out.append(child.text.strip())
                    break
        return out

    tag = root.tag.replace(NS, "")
    if tag == "sitemapindex":
        return [], locs("sitemap")
    if tag == "urlset":
        return locs("url"), []
    return locs("url"), locs("sitemap")


def sitemaps_from_robots(body: str, base: str) -> list[str]:
    """Honour `Sitemap:` lines. Sites that advertise it rarely use sitemap.xml."""
    out = []
    for line in body.splitlines():
        k, _, v = line.partition(":")
        if k.strip().lower() == "sitemap":
            u = normalise(base, v.strip())
            if u:
                out.append(u)
    return out


def from_sitemap(start: str, insecure: bool, timeout: float,
                 log: list[dict], robots_body: str = "") -> list[str]:
    origin = (urllib.parse.urlparse(start).scheme, urllib.parse.urlparse(start).netloc.lower())
    base = f"{origin[0]}://{origin[1]}"
    # Declared locations first, then the conventional guesses.
    queue: list[str] = dedupe(sitemaps_from_robots(robots_body, base))
    queue += [urllib.parse.urljoin(base + "/", c.lstrip("/")) for c in SITEMAP_CANDIDATES]
    found: list[str] = []
    visited: set[str] = set()
    depth = 0

    while queue and depth <= MAX_SITEMAP_DEPTH:
        nxt: list[str] = []
        for sm in queue:
            if sm in visited:
                continue
            visited.add(sm)
            code, body = audit_mod.fetch_optional(sm, insecure)
            if code != 200 or not body.strip():
                continue
            pages, children = parse_sitemap(body)
            log.append({"sitemap": sm, "pages": len(pages), "children": len(children)})
            found.extend(u for u in (normalise(sm, p) for p in pages) if u)
            nxt.extend(c for c in (normalise(sm, c) for c in children) if c)
        # Walk nested sitemaps from the same origin only.
        queue = [u for u in nxt if same_origin(u, origin)]
        depth += 1

    return [u for u in dedupe(found) if same_origin(u, origin)]


def from_links(start: str, depth: int, insecure: bool, timeout: float,
               limit: int, delay: float, log: list[dict]) -> list[str]:
    """Breadth-first over same-origin <a href>, deepest level = --depth."""
    origin = (urllib.parse.urlparse(start).scheme, urllib.parse.urlparse(start).netloc.lower())
    seen: set[str] = set()
    ordered: list[str] = []
    frontier = [start]
    for level in range(depth + 1):
        nxt: list[str] = []
        for url in frontier:
            key = url.rstrip("/") or url
            if key in seen:
                continue
            seen.add(key)
            ordered.append(url)
            if len(ordered) >= limit or level == depth:
                continue
            try:
                html = audit_mod.fetch(url, insecure=insecure)
            except (urllib.error.URLError, OSError, ValueError) as e:
                log.append({"url": url, "error": str(e)})
                continue
            time.sleep(delay)
            page = audit_mod.parse_html(html)
            for href in page.links:
                cand = normalise(url, href)
                if cand and same_origin(cand, origin) and (cand.rstrip("/") or cand) not in seen:
                    nxt.append(cand)
        frontier = dedupe(nxt)
        if not frontier or len(ordered) >= limit:
            break
    return ordered[:limit]


def respectful(robots_body: str | None, ua: str = "*") -> urllib.robotparser.RobotFileParser:
    rp = urllib.robotparser.RobotFileParser()
    try:
        rp.parse((robots_body or "").splitlines())
    except (ValueError, UnicodeError):
        pass
    return rp


# --- aggregation -----------------------------------------------------------

def aggregate(origin: str, source: str, pages: list[dict], refused: list[dict],
              log: list[dict]) -> dict:
    scores = [p["score"] for p in pages if isinstance(p.get("score"), int)]
    scores_sorted = sorted(scores)
    mean = round(sum(scores) / len(scores)) if scores else 0
    median = 0
    if scores_sorted:
        mid = len(scores_sorted) // 2
        median = (scores_sorted[mid] if len(scores_sorted) % 2
                  else round((scores_sorted[mid - 1] + scores_sorted[mid]) / 2))

    # Which checks fail most often? A failure on many pages is a template bug and
    # is worth more than any single page's score.
    tally: dict[str, dict] = {}
    for p in pages:
        for chk in p.get("checks", []):
            if chk["status"] != "fail":
                continue
            t = tally.setdefault(chk["id"], {"id": chk["id"], "count": 0,
                                             "weight": chk["weight"],
                                             "example": chk["detail"]})
            t["count"] += 1
    common = sorted(tally.values(), key=lambda t: (-t["count"], -t["weight"]))[:10]

    worst = sorted(({"url": p["url"], "score": p["score"]} for p in pages),
                   key=lambda x: x["score"])[:5]

    return {
        "site": origin,
        "source": source,
        "urls_audited": len(pages),
        "score_mean": mean,
        "score_median": median,
        "score_min": scores_sorted[0] if scores_sorted else 0,
        "score_max": scores_sorted[-1] if scores_sorted else 0,
        "worst": worst,
        "common_failures": common,
        "skipped": refused,
        "discovery": log,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Audit many pages of one site and aggregate the results.")
    ap.add_argument("url", nargs="?", help="site URL to start from")
    ap.add_argument("--fixture-dir", help="local directory of .html files, no network")
    ap.add_argument("--source", choices=["auto", "sitemap", "links"], default="auto",
                    help="how to discover URLs (default: try sitemap, then links)")
    ap.add_argument("--depth", type=int, default=1,
                    help="link-follow depth for --source links (default 1)")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"max pages to audit (default {DEFAULT_LIMIT}, hard cap {HARD_LIMIT})")
    ap.add_argument("--delay", type=float, default=DEFAULT_DELAY,
                    help=f"seconds between requests (default {DEFAULT_DELAY})")
    ap.add_argument("--json", help="write JSON to this path instead of stdout only")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args(argv)

    if args.limit < 1 or args.limit > HARD_LIMIT:
        print(json.dumps({"error": f"--limit must be 1..{HARD_LIMIT}",
                          "requested": args.limit}), file=sys.stderr)
        return 3

    # --- offline mode: audit a directory of saved HTML ----------------------
    if args.fixture_dir:
        d = Path(args.fixture_dir)
        if not d.is_dir():
            print(json.dumps({"error": f"not a directory: {d}"}), file=sys.stderr)
            return 2
        files = sorted(p for p in d.rglob("*") if p.suffix.lower() in (".html", ".htm"))
        if not files:
            print(json.dumps({"error": f"no .html files in {d}"}), file=sys.stderr)
            return 2
        pages = []
        for f in files[:args.limit]:
            html = f.read_text(encoding="utf-8", errors="replace")
            res = audit_mod.audit(audit_mod.parse_html(html), html, None)
            res["url"] = f.relative_to(d).as_posix()
            pages.append(res)
        report = aggregate(str(d), "fixture-dir", pages, [], [])
        report["pages"] = pages
        blob = json.dumps(report, indent=2, ensure_ascii=False)
        if args.json:
            Path(args.json).write_text(blob, encoding="utf-8")
        if not args.quiet:
            print(blob)
        return 0

    if not args.url:
        ap.error("give a site URL or --fixture-dir")

    start = args.url
    p = urllib.parse.urlparse(start)
    if p.scheme not in ("http", "https") or not p.netloc:
        print(json.dumps({"error": f"not an http(s) URL: {start}"}), file=sys.stderr)
        return 2
    origin = (p.scheme, p.netloc.lower())
    base = f"{p.scheme}://{p.netloc}"

    # Be a good citizen: read the site's own rules before walking it.
    code, robots_body = audit_mod.fetch_optional(base + "/robots.txt", args.insecure)
    rp = respectful(robots_body if code == 200 else "", audit_mod.UA)

    log: list[dict] = []
    refused: list[dict] = []

    source = args.source
    found: list[str] = []
    if source in ("auto", "sitemap"):
        found = from_sitemap(start, args.insecure, 15.0, log,
                             robots_body if code == 200 else "")
        if not found and source == "auto":
            source = "links"
        elif found:
            source = "sitemap"
    if source == "links" or (args.source == "links"):
        source = "links"
        found = from_links(start, args.depth, args.insecure, 15.0, args.limit,
                           args.delay, log)

    if not found:
        print(json.dumps({"error": "no URLs discovered",
                          "site": base, "discovery": log}), file=sys.stderr)
        return 2

    targets: list[str] = []
    for u in found:
        if not same_origin(u, origin):
            refused.append({"url": u, "reason": "off-origin"})
            continue
        if not rp.can_fetch(audit_mod.UA, u):
            refused.append({"url": u, "reason": "robots.txt disallows"})
            continue
        targets.append(u)
        if len(targets) >= args.limit:
            break

    if not targets:
        print(json.dumps({"error": "every discovered URL was refused",
                          "site": base, "skipped": refused}), file=sys.stderr)
        return 2

    pages = []
    for i, u in enumerate(targets):
        if i:
            time.sleep(args.delay)
        try:
            html = audit_mod.fetch(u, insecure=args.insecure)
        except (urllib.error.URLError, OSError, ValueError) as e:
            refused.append({"url": u, "reason": f"fetch failed: {e}"})
            continue
        res = audit_mod.audit(audit_mod.parse_html(html), html, u, args.insecure)
        pages.append(res)

    if not pages:
        print(json.dumps({"error": "no page could be audited",
                          "site": base, "skipped": refused}), file=sys.stderr)
        return 2

    report = aggregate(base, source, pages, refused, log)
    report["pages"] = pages
    blob = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json:
        Path(args.json).write_text(blob, encoding="utf-8")
    if not args.quiet:
        print(blob)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
