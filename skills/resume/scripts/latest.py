"""List the notes a session can resume from, newest first, with what changed after each.

Usage: python latest.py [name] [--root <repo>]

Looks in docs/handoffs, .claude/handoffs and .claude/checkpoints under the repo (and under the
git root when run from a subfolder). Each note carries a name in its banner
("# Handoff 2026-09-21 14:05 · doc-pipeline"); a note from before names existed is known by
the slug of its filename. With a name, only notes of that name are listed and the newest is
the one to resume; without one, every note is listed with its name so the reader can choose.
For the chosen note it prints the commits and dirty files git has seen since its timestamp,
so the reader can tell what the note does not know about.
"""
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

NOTE_DIRS = ("docs/handoffs", ".claude/handoffs", ".claude/checkpoints")
HEADER = re.compile(
    r"^#\s*(Handoff|Checkpoint)\s+(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?"
    r"(?:\s*[·\-–—:]\s*(?P<name>[^\n]+?))?\s*$", re.I | re.M)
SLUG = re.compile(r"^\d{4}-\d{2}-\d{2}-?(.*)$")


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30).stdout.strip()
    except Exception:
        return ""


def describe(path: Path) -> tuple[datetime, str, str]:
    """(timestamp, kind, name) — from the banner; the filename slug names an unnamed note."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        head = ""
    m = HEADER.search(head)
    slug = (SLUG.match(path.stem) or [None, path.stem])[1] or path.stem
    if m:
        when = datetime.strptime(m.group(2) + " " + (m.group(3) or "00:00"), "%Y-%m-%d %H:%M")
        return when, m.group(1).lower(), (m.group("name") or slug).strip().lower()
    return datetime.fromtimestamp(path.stat().st_mtime), "note", slug.lower()


def main() -> int:
    args = sys.argv[1:]
    root_arg = None
    if "--root" in args:
        i = args.index("--root")
        root_arg = args[i + 1]
        del args[i:i + 2]
    want = args[0].strip().lower() if args else None
    start = Path(root_arg or ".").resolve()
    top = git(start, "rev-parse", "--show-toplevel")
    roots = [start] + ([Path(top)] if top and Path(top) != start else [])
    notes: list[tuple[datetime, str, str, Path]] = []
    seen: set[Path] = set()
    for root in roots:
        for d in NOTE_DIRS:
            for f in sorted((root / d).glob("*.md")):
                if f.resolve() in seen:
                    continue
                seen.add(f.resolve())
                when, kind, name = describe(f)
                notes.append((when, kind, name, f))
    if not notes:
        print(f"no handoff or checkpoint notes under {', '.join(str(r) for r in roots)}")
        return 1
    notes.sort(reverse=True)
    picked = [n for n in notes if n[2] == want] if want else notes
    if want and not picked:
        names = sorted({n[2] for n in notes})
        print(f"no note named '{want}'; names here: {', '.join(names)}")
        return 1
    for when, kind, name, f in picked[:8]:
        print(f"{when:%Y-%m-%d %H:%M}  {kind:<10} {name:<24} {f}")
    if want:
        others = sorted({n[2] for n in notes if n[2] != want})
        if others:
            print(f"other names here (sibling sessions'): {', '.join(others)}")
    when, kind, name, newest = picked[0]
    root = Path(top) if top else start
    since = when.strftime("%Y-%m-%dT%H:%M")
    print(f"\nresume from: {newest}")
    log = git(root, "log", "--oneline", f"--since={since}", "--all")
    print(f"commits since {since} (all branches):")
    print(log if log else "  none")
    dirty = git(root, "status", "--short")
    print("dirty now:")
    print(dirty if dirty else "  clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
