#!/usr/bin/env python3
"""Verify install.sh puts the skill in all three agent trees.

Runs the real installer against a throwaway root, asserts the three paths,
asserts the reference files came along, then cleans up.
"""
from __future__ import annotations


import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TREES = [".claude/skills/better-seo", ".codex/skills/better-seo", ".agents/skills/better-seo"]
# command path -> the skill tree that same agent loads
CMD_TREES = {
    ".claude/commands/seo-audit.md": ".claude/skills/better-seo",
    ".codex/commands/seo-audit.md": ".codex/skills/better-seo",
    ".omp/agent/commands/seo-audit.md": ".agents/skills/better-seo",
    ".agents/commands/seo-audit.md": ".agents/skills/better-seo",
}
NEEDED = [
    "SKILL.md",
    "scripts/audit.py",
    "references/agentic-search.md",
    "references/onpage.md",
    "references/technical.md",
]


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
        # The installed skill must never ship local test bytecode.
        for tree in TREES:
            junk = [p for p in (Path(tmp) / tree).rglob("*")
                    if p.name == "__pycache__" or p.suffix == ".pyc"]
            label = "no bytecode in installed skill"
            if junk:
                print(f"FAIL  {label}: {[str(j) for j in junk]}")
                bad += 1
            else:
                print(f"PASS  {label} ({tree})")

        for cmd, skill_tree in CMD_TREES.items():
            p = Path(tmp) / cmd
            if not p.is_file():
                print(f"FAIL  missing {cmd}")
                bad += 1
                continue
            text = p.read_text(encoding="utf-8")
            if "@SKILL_DIR@" in text:
                print(f"FAIL  {cmd} still has an unsubstituted placeholder")
                bad += 1
                continue
            # Every copy must point at the skill tree its own agent loads.
            want = str(Path(tmp) / skill_tree).replace("\\", "/")
            if want not in text.replace("\\", "/"):
                print(f"FAIL  {cmd} does not reference {skill_tree}")
                bad += 1
                continue
            # ...and the resolver must actually find it. A matching string is not
            # enough: an MSYS '/c/Users/...' path matched here but made Windows
            # Python look for C:\c\Users\...
            snippet = extract_snippet(text)
            if not snippet:
                print(f"FAIL  {cmd} has no runnable resolver snippet")
                bad += 1
                continue
            found = run_resolver(bash, snippet)
            want_cli = str(Path(tmp) / skill_tree / "scripts" / "audit.py")
            if found and Path(found).resolve() == Path(want_cli).resolve():
                print(f"PASS  {cmd} -> {skill_tree} (resolves)")
            else:
                print(f"FAIL  {cmd} resolves {found or 'nothing'}, want {want_cli}")
                bad += 1

        if bad:
            return 1

        # The installed skill must be runnable from an unrelated cwd: its CLI
        # lives inside the skill folder, not at the repo root.
        installed = Path(tmp) / TREES[0] / "scripts" / "audit.py"
        fixture = ROOT / "tests" / "fixtures" / "good.html"
        r = subprocess.run([sys.executable, str(installed), "--fixture", str(fixture), "--quiet"],
                           capture_output=True, text=True, cwd=tmp)
        if r.returncode == 0:
            print("PASS  installed audit.py runs from a foreign cwd")
        else:
            print(f"FAIL  installed audit.py failed: {r.stderr.strip()}")
            bad += 1

    # A sandbox root given as a Windows path never exercises the MSYS
    # normalisation above, which is exactly how a '/c/Users/...' path shipped
    # unnoticed. Install again with the POSIX form Git Bash's $HOME produces.
    bad += install_with_posix_root(bash)
    bad += resolver_survives_missing_home(bash)
    return 1 if bad else 0


def resolver_survives_missing_home(bash: str) -> int:
    """The command must still find the CLI when the agent shell lacks HOME.

    Reproduced live: an omp session ran the command with HOME unset, so every
    ~/ probe became /.omp/... and the resolver printed an empty CLI.
    """
    src = (ROOT / "commands" / "seo-audit.md").read_text(encoding="utf-8")
    snippet = extract_snippet(src)
    if not snippet:
        print("FAIL  command has no resolver snippet")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        # A plugin-shaped tree, installed under a fake home with no HOME var.
        home = Path(tmp) / "home"
        skill = home / ".omp/plugins/node_modules/better-seo/skills/better-seo"
        shutil.copytree(ROOT / "skills/better-seo", skill)
        script = Path(tmp) / "resolver.sh"
        script.write_text(snippet, encoding="utf-8", newline="\n")

        fails = 0
        for label, prelude in [
            ("HOME set", f"export HOME='{home}'"),
            ("HOME unset", f"unset HOME; export USERPROFILE='{home}'"),
        ]:
            # Neutral cwd: from the repo root the command's "current directory"
            # fallback would find the checkout and mask a broken home probe.
            r = subprocess.run([bash, "-c", f"{prelude}; bash '{script}'"],
                               capture_output=True, text=True, timeout=60, cwd=tmp)
            line = [ln for ln in r.stdout.splitlines() if ln.startswith("CLI=")]
            got = line[-1][4:].strip() if line else ""
            if got and Path(got).is_file():
                print(f"PASS  resolver finds the CLI with {label}")
            else:
                print(f"FAIL  resolver with {label} printed {got or 'nothing'}")
                fails += 1
        return fails


def extract_snippet(text: str) -> str:
    """Pull the resolver shell block out of a command file."""
    m = re.search(r"```bash\n(.*?)```", text, re.S)
    return m.group(1) if m else ""


def run_resolver(bash: str, snippet: str) -> str:
    """Execute the command's own resolver and return the CLI path it prints."""
    r = subprocess.run([bash, "-c", snippet], capture_output=True, text=True, timeout=60)
    # The snippet prints "CLI=<path>"; take the last non-empty line.
    lines = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    if not lines:
        return ""
    return lines[-1].removeprefix("CLI=")


def install_with_posix_root(bash: str) -> int:
    """dest-root in MSYS form, as Git Bash's $HOME yields."""
    with tempfile.TemporaryDirectory() as tmp:
        posix = subprocess.run([bash, "-c", 'cygpath -u "$1"', "-", tmp],
                               capture_output=True, text=True).stdout.strip()
        if not posix.startswith("/"):
            print("SKIP: no MSYS path form available (not Git Bash)")
            return 0

        r = subprocess.run([bash, str(ROOT / "install.sh"), "--dest-root", posix],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"FAIL  install with POSIX root exited {r.returncode}: {r.stderr.strip()}")
            return 1

        cmd = Path(tmp) / ".agents/commands/seo-audit.md"
        if not cmd.is_file():
            print(f"FAIL  missing {cmd}")
            return 1
        snippet = extract_snippet(cmd.read_text(encoding="utf-8"))
        if not snippet:
            print("FAIL  POSIX-root command has no resolver snippet")
            return 1
        target = run_resolver(bash, snippet)
        if not target:
            print("FAIL  POSIX-root command resolved nothing")
            return 1
        # The written path must resolve under the OS the agent runs on, not just
        # inside the shell that installed it.
        if Path(target).is_file():
            print("PASS  POSIX dest-root yields a path the OS can resolve")
            return 0
        print(f"FAIL  POSIX dest-root wrote an unusable path: {target}")
        return 1


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
