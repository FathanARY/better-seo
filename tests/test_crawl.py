#!/usr/bin/env python3
"""Assert the site crawler discovers, refuses and aggregates correctly, offline."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CRAWL = ROOT / "skills" / "better-seo" / "scripts" / "crawl.py"
SITE = ROOT / "tests" / "fixtures" / "site"

sys.path.insert(0, str(CRAWL.parent))
import crawl  # noqa: E402


def run(*args, timeout=120):
    r = subprocess.run([sys.executable, str(CRAWL), *args],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


URLSET = ('<?xml version="1.0"?>'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          '<url><loc>https://a.test/</loc></url>'
          '<url><loc>https://a.test/pricing</loc></url>'
          '</urlset>')
SITEMAP_INDEX = ('<?xml version="1.0"?>'
                 '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                 '<sitemap><loc>https://a.test/s1.xml</loc></sitemap>'
                 '<sitemap><loc>https://a.test/s2.xml</loc></sitemap>'
                 '</sitemapindex>')
NO_NS = ('<?xml version="1.0"?><urlset>'
         '<url><loc>https://a.test/x</loc></url></urlset>')


def main() -> int:
    fails = 0
    checks: list[tuple[str, bool]] = []

    # --- sitemap parsing ------------------------------------------------------
    pages, children = crawl.parse_sitemap(URLSET)
    checks.append(("<loc> is read from inside <url>", pages == ["https://a.test/", "https://a.test/pricing"]))
    checks.append(("urlset yields no child sitemaps", children == []))
    pages, children = crawl.parse_sitemap(SITEMAP_INDEX)
    checks.append(("sitemapindex yields child sitemaps",
                   children == ["https://a.test/s1.xml", "https://a.test/s2.xml"]))
    checks.append(("sitemapindex yields no page urls", pages == []))
    pages, _ = crawl.parse_sitemap(NO_NS)
    checks.append(("a namespace-less sitemap still parses", pages == ["https://a.test/x"]))
    checks.append(("malformed xml returns empty, not a crash",
                   crawl.parse_sitemap("<not xml") == ([], [])))
    checks.append(("html served instead of xml returns empty",
                   crawl.parse_sitemap("<!DOCTYPE html><html></html>") == ([], [])))

    # --- robots.txt sitemap discovery ----------------------------------------
    robots = ("User-agent: *\nDisallow: /private\n"
              "Sitemap: https://a.test/sitemap_marketing.xml\n"
              "sitemap: https://a.test/second.xml\n")
    got = crawl.sitemaps_from_robots(robots, "https://a.test")
    checks.append(("Sitemap: directives are honoured, any case",
                   got == ["https://a.test/sitemap_marketing.xml",
                           "https://a.test/second.xml"]))
    checks.append(("no Sitemap: line yields nothing",
                   crawl.sitemaps_from_robots("User-agent: *\nDisallow:\n", "https://a.test") == []))
    checks.append(("a relative Sitemap: value is resolved",
                   crawl.sitemaps_from_robots("Sitemap: /sm.xml", "https://a.test")
                   == ["https://a.test/sm.xml"]))

    # --- URL hygiene ---------------------------------------------------------
    n = crawl.normalise
    checks.append(("fragment is stripped",
                   n("https://a.test/", "/x#frag") == "https://a.test/x"))
    checks.append(("relative resolves against the page",
                   n("https://a.test/a/b", "../c") == "https://a.test/c"))
    for bad in ("mailto:x@y.z", "tel:+1", "javascript:void(0)", "", "   "):
        checks.append((f"{bad or 'empty'} href is not crawlable", n("https://a.test/", bad) is None))

    d = crawl.dedupe(["https://a.test/x", "https://a.test/x/", "https://a.test/y"])
    checks.append(("trailing-slash duplicate is collapsed", d == ["https://a.test/x", "https://a.test/y"]))

    # --- robots refusal -------------------------------------------------------
    rp = crawl.respectful("User-agent: *\nDisallow: /private\n")
    checks.append(("robots refuses a disallowed path", not rp.can_fetch("*", "https://a.test/private/x")))
    checks.append(("robots allows the rest", rp.can_fetch("*", "https://a.test/public")))
    checks.append(("a missing robots.txt allows everything",
                   crawl.respectful("").can_fetch("*", "https://a.test/anything")))

    # --- offline directory crawl ---------------------------------------------
    code, out, err = run("--fixture-dir", str(SITE))
    checks.append(("fixture-dir exits 0", code == 0))
    report = json.loads(out) if out.strip() else {}
    checks.append(("fixture-dir audits every page", report.get("urls_audited") == 4))
    checks.append(("fixture-dir reports per-page results", len(report.get("pages", [])) == 4))
    checks.append(("aggregate has a mean", isinstance(report.get("score_mean"), int)))
    checks.append(("aggregate has a median", isinstance(report.get("score_median"), int)))
    checks.append(("min <= median <= max",
                   report.get("score_min", 999) <= report.get("score_median", 0)
                   <= report.get("score_max", -1)))
    worst = report.get("worst", [])
    checks.append(("worst is sorted ascending", [w["score"] for w in worst] == sorted(w["score"] for w in worst)))
    checks.append(("worst lists the bad pages first",
                   worst and worst[0]["score"] == report["score_min"]))

    common = report.get("common_failures", [])
    checks.append(("common failures are ranked by page count",
                   len(common) >= 2 and common[0]["count"] >= common[1]["count"]))
    # Both bad fixtures lack a meta description and an h1, so those must lead.
    ids = [c["id"] for c in common]
    checks.append(("a shared failure surfaces", "meta_description" in ids))
    checks.append(("shared failures carry an example detail",
                   all(c.get("example") for c in common)))

    # --limit must cap the fixture-dir run too.
    code, out, _ = run("--fixture-dir", str(SITE), "--limit", "2")
    limited = json.loads(out)
    checks.append(("--limit caps the fixture-dir run", limited["urls_audited"] == 2))

    # --- guardrails -----------------------------------------------------------
    code, _, err = run("https://example.com", "--limit", "500")
    checks.append(("over-cap limit exits 3", code == 3))
    checks.append(("over-cap limit explains the cap", "1..200" in err))
    code, _, _ = run("https://example.com", "--limit", "0")
    checks.append(("zero limit exits 3", code == 3))
    code, _, _ = run("ftp://example.com")
    checks.append(("non-http url exits 2", code == 2))
    code, _, _ = run("--fixture-dir", str(Path(tempfile.gettempdir()) / "nope-nonexistent"))
    checks.append(("missing fixture dir exits 2", code == 2))
    with tempfile.TemporaryDirectory() as tmp:
        code, _, err = run("--fixture-dir", tmp)
        checks.append(("empty fixture dir exits 2", code == 2))

    # --- --json writes the file ----------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        jp = Path(tmp) / "site.json"
        code, out, _ = run("--fixture-dir", str(SITE), "--json", str(jp), "--quiet")
        checks.append(("--json writes the file", code == 0 and jp.is_file()))
        checks.append(("--quiet suppresses stdout", out.strip() == ""))
        written = json.loads(jp.read_text(encoding="utf-8"))
        checks.append(("written json matches the report shape",
                       {"site", "source", "urls_audited", "score_mean",
                        "worst", "common_failures", "pages"} <= set(written)))

    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails += 1

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
