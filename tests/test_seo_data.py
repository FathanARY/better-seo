#!/usr/bin/env python3
"""Assert the data scripts fail honestly and parse real payload shapes.

Nothing here touches the network or needs credentials. Both scripts are exercised
through their NotConfigured / Missing paths, which is exactly what a user with no
setup sees.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GSC = ROOT / "skills" / "better-seo-data" / "scripts" / "gsc.py"
CWV = ROOT / "skills" / "better-seo-data" / "scripts" / "cwv.py"

sys.path.insert(0, str(GSC.parent))
import gsc  # noqa: E402
import cwv  # noqa: E402


def run(script: Path, *args, env_extra=None, timeout=120):
    env = {k: v for k, v in os.environ.items()
           if k not in ("GSC_ACCESS_TOKEN", "GSC_CREDENTIALS")}
    env.pop("GSC_API_BASE", None)
    # Point at an empty HOME so a real credentials file cannot leak into the test.
    with tempfile.TemporaryDirectory() as fake_home:
        env["HOME"] = fake_home
        env["USERPROFILE"] = fake_home
        if env_extra:
            env.update(env_extra)
        r = subprocess.run([sys.executable, str(script), *args],
                           capture_output=True, text=True, timeout=timeout, env=env)
    return r.returncode, r.stdout, r.stderr


def main() -> int:
    fails = 0
    checks: list[tuple[str, bool]] = []

    # --- gsc: no credentials is a normal answer, not a crash -----------------
    code, out, err = run(GSC, "sites")
    checks.append(("gsc without credentials exits 3", code == 3))
    body = {}
    try:
        body = json.loads(err)
    except json.JSONDecodeError:
        pass
    checks.append(("gsc reports not_configured", body.get("error") == "not_configured"))
    detail = body.get("detail", "")
    checks.append(("gsc explains how to set up", "export GSC_ACCESS_TOKEN" in detail))
    checks.append(("gsc names the required scope",
                   "webmasters.readonly" in detail))
    checks.append(("gsc says service accounts are unsupported",
                   "Service-account" in detail))
    checks.append(("gsc prints no traceback", "Traceback" not in err))

    # A malformed credentials file must be explained, not raised.
    with tempfile.TemporaryDirectory() as tmp:
        bad = Path(tmp) / "gsc.json"
        bad.write_text("{not json", encoding="utf-8")
        code, _, err = run(GSC, "sites", "--credentials", str(bad))
        checks.append(("gsc: broken credentials json exits 3", code == 3))
        checks.append(("gsc: broken json names the file", "not valid JSON" in err))

        partial = Path(tmp) / "partial.json"
        partial.write_text('{"client_id":"a"}', encoding="utf-8")
        code, _, err = run(GSC, "sites", "--credentials", str(partial))
        checks.append(("gsc: incomplete credentials exits 3", code == 3))
        checks.append(("gsc: incomplete credentials lists what is missing",
                       "client_secret" in err and "refresh_token" in err))

    # A token path must not be rejected for lack of a file.
    code, _, err = run(GSC, "sites", "--token", "fake", env_extra={
        "GSC_API_BASE": "http://127.0.0.1:9/webmasters/v3"})
    checks.append(("gsc accepts a token without a credentials file",
                   "not_configured" not in err))
    checks.append(("gsc: unreachable API exits 2", code == 2))

    # --- gsc: pure helpers ---------------------------------------------------
    start, end = gsc.date_range(28, 3)
    import datetime as dt
    sd = dt.date.fromisoformat(start)
    ed = dt.date.fromisoformat(end)
    checks.append(("date_range spans exactly the requested days",
                   (ed - sd).days == 27))
    checks.append(("date_range ends before today by the lag",
                   (dt.date.today() - ed).days >= 3))

    rows = [{"keys": ["https://a.test/x"], "clicks": 5, "impressions": 1000,
             "ctr": 0.005, "position": 8.4}]
    got = gsc.summarise(rows, "page")
    checks.append(("summarise flattens the key", got[0]["page"] == "https://a.test/x"))
    checks.append(("summarise converts ctr to a percentage", got[0]["ctr"] == 0.5))
    checks.append(("summarise keeps position to one decimal", got[0]["position"] == 8.4))
    checks.append(("summarise tolerates empty rows", gsc.summarise([], "page") == []))

    pages = [
        {"page": "/high-impressions-low-ctr", "clicks": 3, "impressions": 5000, "ctr": 0.06, "position": 9.0},
        {"page": "/good", "clicks": 300, "impressions": 5000, "ctr": 6.0, "position": 2.0},
        {"page": "/tiny", "clicks": 0, "impressions": 10, "ctr": 0.0, "position": 40.0},
    ]
    opp = gsc.find_opportunities(pages, min_impressions=100, max_ctr=2.0)
    checks.append(("opportunities keeps only low-CTR high-impression pages",
                   [o["page"] for o in opp] == ["/high-impressions-low-ctr"]))
    checks.append(("opportunities ignores pages below the impression floor",
                   all(o["page"] != "/tiny" for o in opp)))

    # --- cwv: grade thresholds match references/technical.md -----------------
    checks.append(("lcp 2000ms is good", cwv.grade(2000, 2500) == "good"))
    checks.append(("lcp 3000ms needs improvement", cwv.grade(3000, 2500) == "needs_improvement"))
    checks.append(("lcp 5000ms is poor", cwv.grade(5000, 2500) == "poor"))
    checks.append(("cls 0.05 is good", cwv.grade(0.05, 0.1) == "good"))
    checks.append(("cls 0.3 is poor", cwv.grade(0.3, 0.1) == "poor"))

    # --- cwv: report parsing on a synthetic Lighthouse payload ---------------
    report = {
        "lighthouseVersion": "12.0.0",
        "finalUrl": "https://a.test/",
        "fetchTime": "2026-01-01T00:00:00Z",
        "configSettings": {"formFactor": "mobile"},
        "categories": {"performance": {"score": 0.62}},
        "audits": {
            "largest-contentful-paint": {"numericValue": 4200, "displayValue": "4.2 s"},
            "cumulative-layout-shift": {"numericValue": 0.05, "displayValue": "0.05"},
            "total-blocking-time": {"numericValue": 700, "displayValue": "700 ms"},
            "first-contentful-paint": {"numericValue": 1500, "displayValue": "1.5 s"},
            "server-response-time": {"numericValue": 300, "displayValue": "300 ms"},
            # Lighthouse 12 uses "metricSavings" for bottleneck audits. A
            # filter keyed on "numeric" silently dropped every real opportunity.
            "unused-javascript": {"score": 0.2, "scoreDisplayMode": "metricSavings",
                                  "title": "Reduce unused JavaScript",
                                  "details": {"overallSavingsMs": 900}},
            "render-blocking-resources": {"score": 0.4, "scoreDisplayMode": "numeric",
                                          "title": "Eliminate render-blocking",
                                          "details": {"overallSavingsMs": 400}},
            "some-passing-check": {"score": 1.0, "scoreDisplayMode": "numeric"},
            "an-informative-audit": {"score": 0.1, "scoreDisplayMode": "informative",
                                     "title": "Just telling you something",
                                     "details": {"overallSavingsMs": 5000}},
            "wasted-bytes-only": {"score": 0.3, "scoreDisplayMode": "metricSavings",
                                  "title": "Drop some bytes",
                                  "details": {"overallSavingsBytes": 400000}},
        },
    }
    parsed = cwv.parse_report(report)
    checks.append(("performance score becomes 0-100", parsed["performance_score"] == 62))
    checks.append(("lcp 4200ms is poor", parsed["vitals"]["lcp"]["status"] == "poor"))
    checks.append(("cls 0.05 is good", parsed["vitals"]["cls"]["status"] == "good"))
    checks.append(("tbt is labelled a lab proxy", "INP" in parsed["vitals"]["tbt"]["note"]))
    failing = [f["metric"] for f in parsed["failing"]]
    checks.append(("failing lists lcp and tbt, not cls", failing == ["lcp", "tbt"]))
    sav = [o["savings_ms"] for o in parsed["opportunities"]]
    checks.append(("opportunities are sorted by savings descending", sav == sorted(sav, reverse=True)))
    checks.append(("the biggest saving comes first",
                   parsed["opportunities"][0]["id"] == "unused-javascript"))
    checks.append(("passing audits are not listed as opportunities",
                   all(o["id"] != "some-passing-check" for o in parsed["opportunities"])))
    checks.append(("informative audits are not opportunities",
                   all(o["id"] != "an-informative-audit" for o in parsed["opportunities"])))
    ids = [o["id"] for o in parsed["opportunities"]]
    checks.append(("metricSavings audits are kept",
                   "unused-javascript" in ids))
    checks.append(("a bytes-only audit still ranks",
                   "wasted-bytes-only" in ids))
    checks.append(("form factor is carried through", parsed["form_factor"] == "mobile"))

    # A report with missing audits must not raise.
    sparse = cwv.parse_report({"categories": {}, "audits": {}})
    checks.append(("a sparse report does not raise", sparse["performance_score"] == 0))
    checks.append(("a sparse report marks unknown metrics",
                   sparse["vitals"]["lcp"]["status"] == "unknown"))

    # --- cwv: toolchain missing is exit 3 with instructions ------------------
    code, out, err = run(CWV, "https://example.com", env_extra={"PATH": ""})
    checks.append(("cwv without toolchain exits 3", code == 3))
    body = {}
    try:
        body = json.loads(err)
    except json.JSONDecodeError:
        pass
    checks.append(("cwv reports missing_toolchain", body.get("error") == "missing_toolchain"))
    detail = body.get("detail", "")
    checks.append(("cwv gives the npx command", "npx --yes lighthouse" in detail))
    checks.append(("cwv says it will not install anything", "never installs" in detail))
    checks.append(("cwv prints no traceback", "Traceback" not in err))

    code, _, err = run(CWV, "ftp://example.com", env_extra={"PATH": ""})
    checks.append(("cwv rejects a non-http url with exit 2", code == 2))

    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails += 1

    fails += test_redaction()

    return 1 if fails else 0


def test_redaction():
    """Credential values must never reach stdout, stderr, or a bug report."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gsc_under_test", ROOT / "skills" / "better-seo-data" / "scripts" / "gsc.py")
    gsc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gsc)
    cases = [
        ('{"client_secret":"abc123","refresh_token":"1//xyz"}', "abc123"),
        ('{"client_secret":"abc123","refresh_token":"1//xyz"}', "1//xyz"),
        ("grant_type=refresh_token&client_secret=s3cr3t", "s3cr3t"),
        ("Authorization failed for ya29.a0AfH6SMBxxxxxxxxxxxxxx", "ya29.a0AfH6SMB"),
    ]
    checks = []
    for text, secret in cases:
        out = gsc.redact(text)
        checks.append((f"redacts {secret[:12]}", secret not in out))
    checks.append(("keeps the key name readable", "client_secret" in gsc.redact('client_secret=x')))
    checks.append(("plain text passes through", gsc.redact("no secrets here") == "no secrets here"))
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    return sum(1 for _, ok in checks if not ok)

if __name__ == "__main__":
    sys.exit(main())
