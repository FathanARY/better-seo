#!/usr/bin/env python3
"""Verify each skill's frontmatter description matches the prompts it must catch.

This does not call a model. It is a cheap regression gate: if a description is
trimmed to something generic, its prompts stop matching and this fails.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# skill dir -> {prompt: keyword groups; ANY phrase from ANY group must appear}
PROMPTS = {
    "better-seo": {
        "audit meta title": ["meta title", "title tag", "meta description", "audit"],
        "why is my page not showing up in ChatGPT": ["chatgpt", "ai search", "ai chatbots", "llm"],
        "how do I get cited by AI Overviews": ["ai search", "ai overview", "cited", "llm"],
        "write schema markup for my product page": ["structured data", "schema"],
        "review my robots.txt for AI crawlers": ["robots.txt", "llms.txt", "ai crawler"],
    },
    "better-seo-build": {
        "set up SEO for my new website": ["set up seo", "seo from scratch", "has no seo", "seo on a new site"],
        "my website has no SEO yet": ["has no seo", "no seo yet", "set up seo", "not configured"],
        "add meta tags to my project": ["meta tags", "metadata", "head tags"],
        "generate robots.txt and sitemap": ["robots.txt", "sitemap"],
        "which framework conventions for SEO": ["next.js", "framework", "conventions"],
    },
}


def description_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit(f"no frontmatter in {path}")
    d = re.search(r"^description:\s*(?:>-?\s*\n)?(.*?)(?:\n\w+:|\Z)", m.group(1), re.S | re.M)
    if not d:
        raise SystemExit(f"no description field in {path}")
    return " ".join(d.group(1).split())


def main() -> int:
    total = ok_total = 0
    for skill, prompts in PROMPTS.items():
        path = ROOT / "skills" / skill / "SKILL.md"
        if not path.is_file():
            print(f"FAIL  missing {path}")
            return 1
        desc = description_of(path).lower()
        print(f"\n{skill}")
        for prompt, groups in prompts.items():
            total += 1
            hit = any(p in desc for p in groups)
            print(f"{'PASS' if hit else 'FAIL'}  {prompt}")
            if hit:
                ok_total += 1
            else:
                print(f"      description missing any of: {groups}")
    print(f"\n{ok_total}/{total}")
    return 0 if ok_total == total else 1


if __name__ == "__main__":
    sys.exit(main())
