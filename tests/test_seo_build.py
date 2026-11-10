#!/usr/bin/env python3
"""Assert the seo-build scaffolder behaves on throwaway projects."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "skills" / "better-seo-build" / "scripts" / "seo_build.py"

sys.path.insert(0, str(BUILD.parent))
import seo_build  # noqa: E402


def run(root: Path, *extra):
    r = subprocess.run([sys.executable, str(BUILD), "--root", str(root), *extra],
                       capture_output=True, text=True, timeout=60)
    return r.returncode, r.stdout, r.stderr


def make(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def main() -> int:
    fails = 0
    checks: list[tuple[str, bool]] = []

    # --- framework detection -------------------------------------------------
    cases = {
        "nextjs-app": {"package.json": "{}", "app/layout.tsx": ""},
        "astro": {"astro.config.mjs": "", "src/pages/index.astro": ""},
        "hugo": {"hugo.toml": ""},
        "jekyll": {"_config.yml": ""},
        "sveltekit": {"svelte.config.js": "", "src/routes/+page.svelte": ""},
        "nuxt": {"nuxt.config.ts": ""},
    }
    with tempfile.TemporaryDirectory() as tmp:
        for want, files in cases.items():
            d = Path(tmp) / want
            d.mkdir(parents=True)
            make(d, files)
            got, _ = seo_build.detect(d)
            checks.append((f"detects {want}", got == want))

        # Empty dir falls back to static, never crashes.
        d = Path(tmp) / "plain"
        d.mkdir()
        got, _ = seo_build.detect(d)
        checks.append(("empty project falls back to static", got == "static"))

        # --- dry run writes nothing -----------------------------------------
        proj = Path(tmp) / "shop"
        proj.mkdir()
        make(proj, {"package.json": '{"name":"shop","homepage":"https://shop.test"}'})
        code, out, err = run(proj)
        report = json.loads(out) if out.strip() else {}
        before = {p for p in proj.rglob("*") if p.is_file()}
        checks.append(("dry run exits 0", code == 0))
        checks.append(("dry run leaves the project untouched",
                       before == {p for p in proj.rglob("*") if p.is_file()}))
        checks.append(("origin read from package.json",
                       report.get("site") == "https://shop.test"))
        checks.append(("origin marked as coming from package.json",
                       report.get("site_source") == "package.json"))
        checks.append(("every planned step is would-write",
                       all(s["action"] in ("would write", "manual") for s in report["steps"])))

        # --- write ------------------------------------------------------------
        code, out, _ = run(proj, "--write", "--quiet")
        checks.append(("write exits 0", code == 0))
        written = {p.relative_to(proj).as_posix() for p in proj.rglob("*") if p.is_file()}
        checks.append(("robots.txt written", "robots.txt" in written))
        checks.append(("sitemap.xml written", "sitemap.xml" in written))
        checks.append(("llms.txt written", "llms.txt" in written))
        checks.append(("head block written", "seo-head.html" in written))
        checks.append(("package.json preserved", "package.json" in written))

        robots = (proj / "robots.txt").read_text(encoding="utf-8")
        for ua in ("GPTBot", "OAI-SearchBot", "PerplexityBot", "ClaudeBot"):
            checks.append((f"robots.txt allows {ua}",
                           any(line.strip() == f"User-agent: {ua}" for line in robots.splitlines())))
        checks.append(("robots.txt references the sitemap", "Sitemap: https://shop.test/sitemap.xml" in robots))

        # --- second run must not overwrite ------------------------------------
        sentinel = "<!-- hand edited -->\n"
        (proj / "robots.txt").write_text(sentinel, encoding="utf-8")
        code, out, _ = run(proj, "--write")
        second = json.loads(out)
        checks.append(("second run reports skipped",
                       all(s["action"] == "skipped (exists)" for s in second["steps"] if s.get("path"))))
        checks.append(("hand-edited file survives a re-run",
                       (proj / "robots.txt").read_text(encoding="utf-8") == sentinel))

        # --- html injection ---------------------------------------------------
        page = proj / "index.html"
        page.write_text(
            "<!DOCTYPE html><html><head><title>Old</title>"
            '<meta name="description" content="old">'
            '<link rel="canonical" href="https://old.test/"></head>'
            "<body><h1>x</h1></body></html>", encoding="utf-8")
        run(proj, "--inject", "index.html", "--site", "https://shop.test",
            "--name", "Shop", "--title", "A real title for the shop",
            "--description", "A real description for the shop page.",
            "--write", "--quiet")
        html = page.read_text(encoding="utf-8")
        checks.append(("injection replaces the old title", "Old" not in html))
        checks.append(("injection keeps exactly one title", html.count("<title>") == 1))
        checks.append(("injection keeps exactly one description",
                       html.count('name="description"') == 1))
        checks.append(("injection keeps exactly one canonical",
                       html.count('rel="canonical"') == 1))
        checks.append(("injection keeps exactly one json-ld block",
                       html.count("application/ld+json") == 1))
        checks.append(("injection uses the new canonical",
                       "https://shop.test/" in html and "old.test" not in html))
        checks.append(("injection lands before </head>",
                       html.index("application/ld+json") < html.index("</head>")))
        checks.append(("injection preserves the body", "<h1>x</h1>" in html))

        # A second inject must not duplicate tags.
        run(proj, "--inject", "index.html", "--site", "https://shop.test",
            "--name", "Shop", "--write", "--quiet")
        html2 = page.read_text(encoding="utf-8")
        checks.append(("re-injection does not duplicate canonical",
                       html2.count('rel="canonical"') == 1))

        # --- guards -----------------------------------------------------------
        code, _, err = run(Path(tmp) / "does-not-exist")
        checks.append(("missing root exits 2", code == 2))
        checks.append(("missing root explains itself", "not a directory" in err))

    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails += 1

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
