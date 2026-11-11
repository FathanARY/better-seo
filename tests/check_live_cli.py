#!/usr/bin/env python3
"""Assert the live CLI produced the checks the skill advertises."""
import json
import sys

d = json.load(open(sys.argv[1]))
assert isinstance(d["score"], int), d
assert 0 <= d["score"] <= 100, d["score"]
ids = {c["id"] for c in d["checks"]}
for need in ("ai_crawler_access", "robots_txt", "indexable", "structured_data"):
    assert need in ids, (need, sorted(ids))
print("score", d["score"], "checks", len(d["checks"]))
