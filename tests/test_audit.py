#!/usr/bin/env python3
"""Assert the audit CLI behaves, offline and against a local server."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "skills" / "better-seo" / "scripts" / "audit.py"
GOOD = ROOT / "tests" / "fixtures" / "good.html"
BAD = ROOT / "tests" / "fixtures" / "bad.html"

sys.path.insert(0, str(AUDIT.parent))
from audit import evaluate_robots  # noqa: E402

ROBOTS = "User-agent: GPTBot\nDisallow: /\n"


def run(path: Path):
    r = subprocess.run([sys.executable, str(AUDIT), "--fixture", str(path), "--quiet"],
                       capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = (ROBOTS if self.path == "/robots.txt"
                else GOOD.read_text(encoding="utf-8")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def serve_and_audit() -> int:
    """Network path must flag a robots.txt that blocks AI crawlers."""
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_port}/page"
        r = subprocess.run([sys.executable, str(AUDIT), url],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            print(f"FAIL  local server audit exit {r.returncode}: {r.stderr.strip()}")
            return 1
        res = json.loads(r.stdout)
        robots = next(c for c in res["checks"] if c["id"] == "robots_txt")
        ok = robots["status"] == "fail" and "GPTBot" in robots["detail"]
        print(f"{'PASS' if ok else 'FAIL'}  network audit flags blocked AI crawler"
              f" ({robots['status']}: {robots['detail']})")
        return 0 if ok else 1
    finally:
        srv.shutdown()


def main() -> int:
    fails = 0

    code, _, err = run(BAD)
    if code != 0:
        print(f"FAIL bad fixture exit {code}: {err}")
        return 1

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

    # robots.txt is judged by what it permits, not by the file existing.
    robots_cases = [
        ("empty robots.txt is allow-all", "", "pass"),
        ("blocking GPTBot fails", "User-agent: GPTBot\nDisallow: /\n", "fail"),
        ("naming GPTBot with Allow passes", "User-agent: GPTBot\nAllow: /\n", "pass"),
        ("path-scoped disallow keeps audited URL", "User-agent: OAI-SearchBot\nDisallow: /private\n", "pass"),
        ("rules for unrelated bots do not count", "User-agent: BadBot\nDisallow: /\n", "pass"),
        ("blanket disallow blocks AI crawlers too", "User-agent: *\nDisallow: /\n", "fail"),
    ]
    for name, body, want in robots_cases:
        got, detail = evaluate_robots(body, "https://x.test/a")
        checks.append((f"{name} -> {want}", got == want))
        if got != want:
            print(f"      got {got}: {detail}")

    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails += 1

    fails += serve_and_audit()

    if fails:
        print(f"\ngood={good['score']} bad={bad['score']}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
