"""Gate self-test: every check the tool makes has a case that must fail and one that must pass.
Run from anywhere; exit 1 if any expectation is missed."""
import subprocess, sys, re
from pathlib import Path

HERE = Path(__file__).parent
AUDIT = Path.home() / ".claude/skills/diagram/scripts/audit.py"


def run(*args):
    r = subprocess.run([sys.executable, str(AUDIT), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=HERE, timeout=300)
    return r.returncode, r.stdout + r.stderr


CASES = [
    # name, args, expected exit, must-appear regexes, must-not-appear regexes
    ("edge with labelled source is seen", ["graph", "edges.mmd"], 0, [r'"from": "A",\s*"to": "B"', r'"endpoint"', r'"classifier"'], []),
    ("deleted arrow is CHANGED", ["diff", "edges.mmd", "edges-arrow-deleted.mmd"], 1, [r"relationships removed\s*: \[\('A', 'B', 0\)\]"], []),
    ("same file is IDENTICAL", ["diff", "edges.mmd", "edges-same.mmd"], 0, [r"before: 20 entities, 15 relationships", r"IDENTICAL"], []),
    ("unmeasurable render refuses", ["check", "xychart.mmd"], 2, [r"\[blocker\] unmeasured"], [r"\[blocker\] illegible"]),
    ("pie slices are entities and its legend is measured", ["check", "pie.mmd"], 0, [r"nodes=2 edges=0", r"pt@target=12\.0"], [r"unparsed", r"unmeasured"]),
    ("changed pie value is DESTROYED", ["diff", "pie.mmd", "pie-value-changed.mmd"], 2, [r"DESTROYED .40."], [r"IDENTICAL"]),
    ("deleted pie slice is CHANGED", ["diff", "pie.mmd", "pie-slice-deleted.mmd"], 1, [r"entities removed\s*: \['beta'\]"], [r"UNVERIFIABLE"]),
    ("unterminated init refuses", ["check", "init-unterminated.mmd"], 2, [r"init-unterminated"], []),
    ("seven participants: needs-author up front", ["check", "seq7.mmd"], 2, [r"needs-author: 7 participants"], []),
    ("message spanning a lifeline is struck through", ["check", "seq-struck.mmd"], 1, [r"\[warning\] spanning-struck: message \"Forward the validated"], [r"\[blocker\]"]),
    ("rightward spanning message pairs with its own arrow, never graded struck-through",
     ["check", "seq-rightward.mmd"], 2, [r"spanning-struck: message \"release lease, reap the mirror results\" spans 3 gaps"], [r"struck-through"]),
    ("graphviz fixed-size overflow", ["check", "gv-overflow.gv"], 2, [r"overflow: label"], []),
    ("forty steps is tall", ["check", "tall.mmd"], 2, [r"\] tall:"], []),
    ("note over twenty words", ["check", "long-note.mmd"], 1, [r"long-note"], [r"\[blocker\]"]),
    ("no false DESTROYED on paths, aliases, e.g., samples, ellipsis, dotted, bare value",
     ["diff", "fp-before.md", "fp-after.md"], 0, [r"VERDICT: IDENTICAL", r"relocated '/api/v2/workorders/123'", r"relocated '1985'", r"sample value '12345'"], [r"DESTROYED"]),
    ("a real deletion still fails", ["diff", "fp-before.md", "fp-after-204-deleted.md"], 2, [r"DESTROYED '204'"], []),
]

bad = 0
for name, args, want_exit, must, must_not in CASES:
    code, out = run(*args)
    misses = [m for m in must if not re.search(m, out)] + [f"unexpected {m}" for m in must_not if re.search(m, out)]
    ok = code == want_exit and not misses
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'}  exit {code} (want {want_exit})  {name}")
    for m in misses:
        print(f"      missing: {m}")
    if not ok:
        print("      " + "\n      ".join(out.strip().splitlines()[-12:]))
print(f"{len(CASES) - bad}/{len(CASES)} gate tests pass")
sys.exit(1 if bad else 0)
