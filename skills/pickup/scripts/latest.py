"""List the notes a session can resume from, newest first, with what changed after each.

Usage: python latest.py [name] [--root <repo>]

Looks in docs/handoffs, .claude/handoffs and .claude/checkpoints under the repo (and under the
git root when run from a subfolder). Each note carries a name in its banner
("# Handoff 2026-09-21 14:05 · doc-pipeline"); a note from before names existed is known by
the slug of its filename. Names are compared case- and separator-insensitively, so a banner's
"Doc Pipeline" and a file named doc-pipeline.md are the same note. With a name, only notes of
that name are listed and the newest is the one to resume; without one, every note is listed
with its name so the reader can choose. For the chosen note it prints the commits and dirty
files git has seen since its timestamp, so the reader can tell what the note does not know
about.
"""
import argparse
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


def normalize_name(s: str) -> str:
    """Case and separators fold to one form, so a banner's "Doc Pipeline" and a filename slug
    "doc-pipeline" compare equal instead of missing each other by a space versus a hyphen."""
    return re.sub(r"[\s_]+", "-", s.strip().lower())


def git(root: Path, *args: str) -> tuple[bool, str]:
    """(ok, output). ok is False both for a nonzero exit and for git failing to run at all — the
    two situations pickup must never present as "nothing happened since the note"."""
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30)
        return r.returncode == 0, (r.stdout.strip() or r.stderr.strip())
    except Exception as e:
        return False, str(e)


def describe(path: Path) -> tuple[datetime, str, str]:
    """(timestamp, kind, name) — from the banner; the filename slug names an unnamed note, or
    stands in when the banner's date is not a real date."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        head = ""
    m = SLUG.match(path.stem)
    slug = m.group(1) if m and m.group(1) else path.stem
    header = HEADER.search(head)
    if not header:
        return datetime.fromtimestamp(path.stat().st_mtime), "note", normalize_name(slug)
    try:
        when = datetime.strptime(header.group(2) + " " + (header.group(3) or "00:00"), "%Y-%m-%d %H:%M")
    except ValueError:
        # The banner has the right shape but not a real date or time (Feb 30, hour 25 — an LLM
        # wrote it by hand). Fall back to the file's mtime rather than losing every other note
        # in the listing to one bad banner.
        when = datetime.fromtimestamp(path.stat().st_mtime)
    name = normalize_name(header.group("name") or slug)
    return when, header.group(1).lower(), name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("name", nargs="?", help="only list notes with this name")
    ap.add_argument("--root", help="repo to look in (default: cwd)")
    args = ap.parse_args(argv)
    want = normalize_name(args.name) if args.name else None
    start = Path(args.root or ".").resolve()
    top_ok, top = git(start, "rev-parse", "--show-toplevel")
    # The cwd, its git root, and any ancestor that keeps notes of its own: a session opened in
    # C:\Code\maestro must still find the note a sibling session left at C:\Code.
    roots = [start] + ([Path(top)] if top_ok and top and Path(top) != start else [])
    for parent in start.parents:
        if any((parent / d).is_dir() for d in NOTE_DIRS) and parent not in roots:
            roots.append(parent)
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
    root = Path(top) if top_ok and top else start
    since = when.strftime("%Y-%m-%dT%H:%M")
    print(f"\nresume from: {newest}")
    print(f"commits since {since} (all branches):")
    log_ok, log = git(root, "log", "--oneline", f"--since={since}", "--all")
    if not log_ok:
        print(f"  git failed: {log or 'could not run git'} — this note cannot know what happened since")
    else:
        print(log if log else "  none")
    print("dirty now:")
    status_ok, dirty = git(root, "status", "--short")
    if not status_ok:
        print(f"  git failed: {dirty or 'could not run git'} — this note cannot know what happened since")
    else:
        print(dirty if dirty else "  clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
