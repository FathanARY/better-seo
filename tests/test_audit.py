#!/usr/bin/env python3
"""Assert the audit CLI behaves on fixtures, offline."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "skills" / "better-seo" / "scripts" / "audit.py"
GOOD = ROOT / "tests" / "fixtures" / "good.html"
BAD = ROOT / "tests" / "fixtures" / "bad.html"


def run(path: Path):
    r = subprocess.run([sys.executable, str(AUDIT), "--fixture", str(path), "--quiet"],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def main() -> int:
    fails = 0

    code, out, err = run(BAD)
    if code != 0:
        print(f"FAIL bad fixture exit {code}: {err}")
        return 1
    # --quiet suppresses stdout; re-read via --json for the assertions
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        jp = Path(tmp) / "bad.json"
        subprocess.run([sys.executable, str(AUDIT), "--fixture", str(BAD),
                        "--quiet", "--json", str(jp)], check=True)
        bad = json.loads(jp.read_text(encoding="utf-8"))
        jp2 = Path(tmp) / "good.json"
        subprocess.run([sys.executable, str(AUDIT), "--fixture", str(GOOD),
                        "--quiet", "--json", str(jp2)], check=True)
        good = json.loads(jp2.read_text(encoding="utf-8"))

    checks = [
        ("bad score is numeric", isinstance(bad["score"], int)),
        ("bad issues non-empty", len(bad["issues"]) > 0),
        ("bad flags noindex", any("noindex" in i for i in bad["issues"])),
        ("bad flags broken jsonld", any("JSON-LD" in i for i in bad["issues"])),
        ("good score numeric", isinstance(good["score"], int)),
        ("good scores higher than bad", good["score"] > bad["score"]),
        ("good has no missing-alt issue", not any("lack alt" in i for i in good["issues"])),
        ("good has issues list", isinstance(good["issues"], list)),
        ("checks carry weight", all("weight" in c for c in good["checks"])),
        ("offline skips network checks",
         all(c["status"] == "skip" for c in good["checks"] if c["id"] in ("robots_txt", "llms_txt"))),
    ]
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails += 1

    if fails:
        print(f"\ngood={good['score']} bad={bad['score']}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
