#!/usr/bin/env python3
"""Verify the better-seo skill triggers on real SEO prompts.

Reads the skill's frontmatter description, then scores each fixture prompt
against the keyword sets the description must cover. Exits 1 if any prompt
misses, printing which keyword each prompt needed.

This tests the description, not a model. It is a cheap regression gate: if
someone trims the description down to "SEO skill", the prompts stop matching
and this fails.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "better-seo" / "SKILL.md"

# prompt -> keyword groups; a prompt matches when ANY phrase from ANY group
# appears (case-insensitive) in the description.
PROMPTS = {
    "audit meta title": [["meta title", "title tag", "meta description", "audit"]],
    "why is my page not showing up in ChatGPT": [["chatgpt", "ai search", "ai chatbots", "llm"]],
    "how do I get cited by AI Overviews": [["ai search", "ai overview", "cited", "llm"]],
    "write schema markup for my product page": [["structured data", "schema"]],
    "review my robots.txt for AI crawlers": [["robots.txt", "llms.txt", "ai crawler"]],
}


def description_of(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit(f"no frontmatter in {SKILL}")
    fm = m.group(1)
    d = re.search(r"^description:\s*(?:>-?\s*\n)?(.*?)(?:\n\w+:|\Z)", fm, re.S | re.M)
    if not d:
        raise SystemExit("no description field in frontmatter")
    return " ".join(d.group(1).split())


def main() -> int:
    desc = description_of(SKILL.read_text(encoding="utf-8"))
    low = desc.lower()
    ok = 0
    for prompt, groups in PROMPTS.items():
        hit = any(p in low for p in groups[0])
        print(f"{'PASS' if hit else 'FAIL'}  {prompt}")
        if hit:
            ok += 1
        else:
            print(f"      missing any of: {groups[0]}")
    print(f"\n{ok}/{len(PROMPTS)}")
    return 0 if ok == len(PROMPTS) else 1


if __name__ == "__main__":
    sys.exit(main())
