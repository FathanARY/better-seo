#!/usr/bin/env python3
"""Verify install.sh puts the skill in all three agent trees.

Runs the real installer against a throwaway root, asserts the three paths,
asserts the reference files came along, then cleans up.
"""
from __future__ import annotations


import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TREES = [".claude/skills/better-seo", ".codex/skills/better-seo", ".agents/skills/better-seo"]
NEEDED = ["SKILL.md", "references/agentic-search.md", "references/onpage.md", "references/technical.md"]


def main() -> int:
    bash = find_bash()
    if bash is None:
        print("SKIP: no working bash")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            [bash, str(ROOT / "install.sh"), "--dest-root", tmp],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(r.stdout, r.stderr, sep="\n")
            print("FAIL: install.sh exited nonzero")
            return 1
        bad = 0
        for tree in TREES:
            for f in NEEDED:
                p = Path(tmp) / tree / f
                if p.is_file():
                    print(f"PASS  {tree}/{f}")
                else:
                    print(f"FAIL  missing {tree}/{f}")
                    bad += 1
        return 1 if bad else 0


def find_bash() -> str | None:
    """First bash that actually runs. On Windows the WSL stub on PATH is a trap."""
    cands = ["bash"] + [str(p) for p in (
        Path(r"C:\Program Files\Git\bin\bash.exe"),
        Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        Path("/bin/bash"), Path("/usr/bin/bash"),
    ) if p.is_file()]
    for c in cands:
        try:
            r = subprocess.run([c, "-c", "echo ok"], capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        if r.returncode == 0 and "ok" in r.stdout:
            return c
    return None


if __name__ == "__main__":
    sys.exit(main())
