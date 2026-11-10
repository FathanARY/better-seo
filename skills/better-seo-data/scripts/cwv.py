#!/usr/bin/env python3
"""Core Web Vitals via Lighthouse. Stdlib only, but requires Chrome + Node.

Lives inside the better-seo-data skill; run it by path.

    python <skill-dir>/scripts/cwv.py https://example.com
    python <skill-dir>/scripts/cwv.py https://example.com --json cwv.json
    python <skill-dir>/scripts/cwv.py https://example.com --mobile

Why a separate script and a separate skill: this takes 30-60 seconds per page
and needs Chromium. audit.py answers in about a second with the stdlib only, and
make check runs offline. Mixing them would cost that.

Exit 0 on success, 2 when Lighthouse cannot run or fails, 3 when the toolchain
is missing (with install instructions, never a stack trace).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Lighthouse's own "good" thresholds, matching references/technical.md.
THRESHOLDS = {"lcp": 2500.0, "inp": 200.0, "cls": 0.1, "fcp": 1800.0, "ttfb": 800.0}

AUDIT_KEYS = {
    "lcp": "largest-contentful-paint",
    "cls": "cumulative-layout-shift",
    "fcp": "first-contentful-paint",
    "ttfb": "server-response-time",
}

MISSING_HELP = """\
Lighthouse is not available. Either path works:

  1. Run it through npx, no global install:
       npx --yes lighthouse@12 "$URL" --output=json --output-path=OUT --quiet \\
         --chrome-flags="--headless=new"

  2. Install it once:
       npm install -g lighthouse
     then make sure a Chrome or Chromium binary is on PATH (or set CHROME_PATH).

This script never installs anything for you. Report the gap instead."""


class Missing(Exception):
    """Toolchain absent. Exit 3."""


class Failed(Exception):
    """Lighthouse ran but did not produce usable output. Exit 2."""


def find_lighthouse() -> list[str]:
    exe = shutil.which("lighthouse")
    if exe:
        return [exe]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "lighthouse@12"]
    raise Missing(MISSING_HELP)


def grade(value: float, good: float) -> str:
    if value <= good:
        return "good"
    if value <= good * 1.6:
        return "needs_improvement"
    return "poor"


def parse_report(report: dict) -> dict:
    audits = report.get("audits") or {}
    def tidy(num):
        """Lighthouse hands back raw floats; 240.68200000000002 is not a metric."""
        if num is None:
            return None
        return round(num, 3) if num < 1 else round(num)

    values = {}
    for short, key in AUDIT_KEYS.items():
        a = audits.get(key) or {}
        num = a.get("numericValue")
        # displayValue for server-response-time is a sentence, not a duration.
        display = a.get("displayValue")
        if short == "ttfb" and num is not None:
            display = f"{round(num)} ms"
        values[short] = {"ms" if short != "cls" else "score": tidy(num),
                         "display": display,
                         "status": grade(num, THRESHOLDS[short]) if num is not None else "unknown"}

    # INP is a field metric. The lab equivalent Lighthouse reports is TBT.
    tbt = (audits.get("total-blocking-time") or {}).get("numericValue")
    values["tbt"] = {"ms": tidy(tbt), "status": grade(tbt, THRESHOLDS["inp"]) if tbt is not None else "unknown",
                     "note": "lab proxy for INP; INP itself needs field data (CrUX)"}

    failing = []
    for short in ("lcp", "cls", "tbt"):
        v = values[short]
        if v["status"] in ("needs_improvement", "poor"):
            failing.append({"metric": short, "status": v["status"],
                            "display": v.get("display")})

    # The heaviest opportunities Lighthouse already computed.
    # Lighthouse 12 reports bottleneck audits with scoreDisplayMode
    # "metricSavings", not "numeric". Filtering on mode drops the useful ones,
    # so rank on measured savings instead and skip only informative noise.
    opps = []
    for key, a in audits.items():
        if a.get("score") is None or a.get("score") >= 0.9:
            continue
        if a.get("scoreDisplayMode") in ("informative", "notApplicable", "manual"):
            continue
        details = a.get("details") or {}
        savings = details.get("overallSavingsMs")
        if savings is None:
            # Some audits carry no timing; rank them by wasted bytes instead.
            savings = 0
            wasted = details.get("overallSavingsBytes") or 0
            if wasted:
                savings = round(wasted / 1000)  # 1 ms per wasted KB, a rough stand-in
        if savings > 50:
            opps.append({"id": key, "title": a.get("title"),
                         "savings_ms": round(savings)})
    opps.sort(key=lambda o: -o["savings_ms"])

    return {
        "performance_score": round(((report.get("categories") or {})
                                    .get("performance", {}).get("score") or 0) * 100),
        "vitals": values,
        "failing": failing,
        "opportunities": opps[:8],
        "lighthouse_version": report.get("lighthouseVersion"),
        "final_url": report.get("finalUrl") or report.get("finalDisplayedUrl"),
        "fetch_time": report.get("fetchTime"),
        "form_factor": (report.get("configSettings") or {}).get("formFactor", "unknown"),
    }


def run_lighthouse(url: str, mobile: bool, extra: list[str]) -> dict:
    cmd = find_lighthouse()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "lh.json"
        argv = cmd + [
            url,
            "--output=json",
            f"--output-path={out}",
            "--quiet",
            "--only-categories=performance",
            "--chrome-flags=--headless=new --no-sandbox",
        ]
        argv += list(extra)
        if not mobile:
            argv.append("--preset=desktop")
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=300)
        except subprocess.TimeoutExpired:
            raise Failed("Lighthouse timed out after 300s")
        if not out.is_file():
            tail = (proc.stderr or proc.stdout or "").strip()[-600:]
            raise Failed(f"Lighthouse produced no report (exit {proc.returncode}). {tail}")
        try:
            return json.loads(out.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise Failed(f"Lighthouse report was not valid JSON: {e}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure Core Web Vitals with Lighthouse.")
    ap.add_argument("url")
    ap.add_argument("--json", help="write the parsed result to this path")
    ap.add_argument("--raw", help="also save the raw Lighthouse report here")
    ap.add_argument("--mobile", action="store_true",
                    help="mobile emulation (Lighthouse's default; desktop is the opt-out)")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--lighthouse-arg", action="append", default=[],
                    help="extra argument passed through to Lighthouse")
    args = ap.parse_args(argv)

    if not args.url.startswith(("http://", "https://")):
        print(json.dumps({"error": f"not an http(s) URL: {args.url}"}), file=sys.stderr)
        return 2

    try:
        report = run_lighthouse(args.url, args.mobile, args.lighthouse_arg)
    except Missing as e:
        print(json.dumps({"error": "missing_toolchain", "detail": str(e)},
                         ensure_ascii=False), file=sys.stderr)
        return 3
    except Failed as e:
        print(json.dumps({"error": "lighthouse_failed", "detail": str(e)},
                         ensure_ascii=False), file=sys.stderr)
        return 2

    result = parse_report(report)
    result["url"] = args.url
    result["caveat"] = ("Lighthouse reports lab data from one synthetic run. "
                        "Real-user INP needs field data (CrUX or the Web Vitals JS).")

    if args.raw:
        Path(args.raw).write_text(json.dumps(report), encoding="utf-8")
    blob = json.dumps(result, indent=2, ensure_ascii=False)
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
