"""Gate self-test: every check the tool makes has a case that must fail and one that must pass.
Run from anywhere; exit 1 if any expectation is missed."""
import importlib.util, json, subprocess, sys, re, tempfile
from pathlib import Path

HERE = Path(__file__).parent
AUDIT = HERE.parent / "scripts" / "audit.py"


def run(*args):
    r = subprocess.run([sys.executable, str(AUDIT), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=HERE, timeout=300)
    return r.returncode, r.stdout + r.stderr


CASES = [
    # name, args, expected exit, must-appear regexes, must-not-appear regexes
    ("a titled, captioned figure has no label finding",
     ["check", "labels-good.md"], 0, [r"labels-good\.md#0"], [r"untitled", r"uncaptioned", r"generic-title", r"long-caption"]),
    ("a figure with no title and no caption is two blockers",
     ["check", "labels-missing.md"], 2, [r"\[blocker\] untitled:", r"\[blocker\] uncaptioned:"], []),
    ("a title that names only the kind of picture, and a long caption, are blockers",
     ["check", "labels-generic.md"], 2, [r"\[blocker\] generic-title:", r"\[blocker\] long-caption: caption is 17 words"], [r"untitled"]),
    ("a caption that repeats the title is a warning",
     ["check", "labels-repeat.md"], 1, [r"\[warning\] caption-repeats-title"], [r"blocker"]),
    ("a raw .mmd carries no title or caption of its own; the embedding document does",
     ["check", "edges.mmd"], None, [r"edges\.mmd#0"], [r"untitled", r"uncaptioned"]),
    ("edge with labelled source is seen", ["graph", "edges.mmd"], 0, [r'"from": "A",\s*"to": "B"', r'"endpoint"', r'"classifier"'], []),
    ("deleted arrow is CHANGED", ["diff", "edges.mmd", "edges-arrow-deleted.mmd"], 1, [r"relationships removed\s*: \[\('A', 'B', 0\)\]"], [r"VERDICT: IDENTICAL", r"entities removed\s*:\s*\["]),
    ("same file is IDENTICAL", ["diff", "edges.mmd", "edges-same.mmd"], 0, [r"before: 20 entities, 15 relationships", r"IDENTICAL"], []),
    ("unmeasurable render refuses", ["check", "xychart.mmd"], 2, [r"\[blocker\] unmeasured"], [r"\[blocker\] illegible"]),
    ("pie slices are entities and its legend is measured", ["check", "pie.mmd"], 0, [r"nodes=2 edges=0", r"pt@target=12\.0"], [r"unparsed", r"unmeasured"]),
    ("changed pie value is DESTROYED", ["diff", "pie.mmd", "pie-value-changed.mmd"], 2, [r"DESTROYED .40."], [r"IDENTICAL"]),
    ("deleted pie slice is CHANGED", ["diff", "pie.mmd", "pie-slice-deleted.mmd"], 1, [r"entities removed\s*: \['beta'\]"], [r"UNVERIFIABLE"]),
    ("unterminated init refuses", ["check", "init-unterminated.mmd"], 2, [r"init-unterminated"], [r"illegible", r"unmeasured"]),
    ("seven participants: needs-author up front", ["check", "seq7.mmd"], 2, [r"needs-author: 7 participants"], [r"no-render", r"unmeasured"]),
    ("message spanning a lifeline is struck through", ["check", "seq-struck.mmd"], 1, [r"\[warning\] spanning-struck: message \"Forward the validated"], [r"\[blocker\]"]),
    ("rightward spanning message pairs with its own arrow, never graded struck-through",
     ["check", "seq-rightward.mmd"], 2, [r"spanning-struck: message \"release lease, reap the mirror results\" spans 3 gaps"], [r"struck-through"]),
    ("graphviz fixed-size overflow", ["check", "gv-overflow.gv"], 2, [r"overflow: label"], [r"no-render", r"unmeasured"]),
    ("forty steps is tall", ["check", "tall.mmd"], 2, [r"\] tall:"], [r"illegible"]),
    ("note over twenty words", ["check", "long-note.mmd"], 1, [r"long-note"], [r"\[blocker\]"]),
    ("no false DESTROYED on paths, aliases, e.g., samples, ellipsis, dotted, bare value",
     ["diff", "fp-before.md", "fp-after.md"], 0, [r"VERDICT: IDENTICAL", r"relocated '/api/v2/workorders/123'", r"relocated '1985'", r"sample value '12345'"], [r"DESTROYED"]),
    ("a real deletion still fails", ["diff", "fp-before.md", "fp-after-204-deleted.md"], 2, [r"DESTROYED '204'"], [r"sample value '204'"]),
    ("declare accepts a node moved whole into a matching table row",
     ["diff", "declare-before.md", "declare-after-right.md", "--declare", "moved to table"], 0,
     [r"VERDICT: RESTRUCTURED"], [r"DESTROYED"]),
    ("declare refuses a table row with the right code but the wrong name",
     ["diff", "declare-before.md", "declare-after-wrong.md", "--declare", "moved to table"], 2,
     [r"DESTROYED 'B'"], [r"RESTRUCTURED"]),
    ("class member drop is CHANGED", ["diff", "class-before.mmd", "class-after-member-deleted.mmd"], 1,
     [r"members changed on 'Foo': -\['bar'\] \+\[\]"], [r"IDENTICAL"]),
    ("ER relationship drop is CHANGED", ["diff", "er-before.mmd", "er-after-rel-deleted.mmd"], 1,
     [r"relationships removed\s*: \[\('CUSTOMER', 'ORDER', 0\)\]"], [r"IDENTICAL"]),
    ("state transition drop is CHANGED", ["diff", "state-before.mmd", "state-after-transition-deleted.mmd"], 1,
     [r"entities removed\s*: \['Running'\]"], [r"IDENTICAL"]),
    ("gantt task drop is CHANGED", ["diff", "gantt-before.mmd", "gantt-after-task-deleted.mmd"], 1,
     [r"entities removed\s*: \['a1'\]"], [r"IDENTICAL"]),
    ("mindmap leaf drop is CHANGED", ["diff", "mindmap-before.mmd", "mindmap-after-leaf-deleted.mmd"], 1,
     [r"entities removed\s*: \['idea two'\]"], [r"IDENTICAL"]),
    ("an unparsed kind (journey) abstains as UNVERIFIABLE, exit 3",
     ["diff", "journey-before.mmd", "journey-after.mmd"], 3, [r"VERDICT: UNVERIFIABLE"], [r"IDENTICAL", r"CHANGED"]),
    ("a split into two afters is IDENTICAL to the one before",
     ["diff", "split-before.mmd", "split-after-1.mmd", "split-after-2.mmd"], 0,
     [r"VERDICT: IDENTICAL", r"before: 3 entities, 2 relationships"], [r"CHANGED", r"DESTROYED"]),
    ("without --context a relocated detail off-page is DESTROYED",
     ["diff", "context-before.mmd", "context-after.mmd"], 2, [r"DESTROYED '404'"], [r"IDENTICAL"]),
    ("--context finds the relocated detail in the named page",
     ["diff", "context-before.mmd", "context-after.mmd", "--context", "context-legend.md"], 0,
     [r"relocated '404'.*context-legend\.md"], [r"DESTROYED"]),
    ("the audit command walks a path and reports a summary",
     ["audit", "edges.mmd", "--target", "md"], 0,
     [r"1 diagrams in 1 files, target md", r"by type\s*: \{'flowchart': 1\}"], []),
    ("a ~~~ mermaid fence in a document is seen and gated",
     ["check", "tilde-fence.md"], 0, [r"tilde-fence\.md#0\s+flowchart"], []),
    ("a ```dot fence in a document is seen and measured",
     ["check", "redraw-dot.md"], 0, [r"redraw-dot\.md#0\s+graphviz/.*pt@target=\d"], [r"unmeasured"]),
    ("a mermaid redraw escalated to Graphviz, same graph, is IDENTICAL",
     ["diff", "redraw-mermaid.md", "redraw-dot.md"], 0, [r"\(graphviz, parsed\)", r"VERDICT: IDENTICAL"], [r"UNVERIFIABLE"]),
]

bad = 0
for name, args, want_exit, must, must_not in CASES:
    code, out = run(*args)
    misses = [m for m in must if not re.search(m, out)] + [f"unexpected {m}" for m in must_not if re.search(m, out)]
    ok = (want_exit is None or code == want_exit) and not misses   # None: the exit is not the point
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'}  exit {code} (want {want_exit})  {name}")
    for m in misses:
        print(f"      missing: {m}")
    if not ok:
        print("      " + "\n      ".join(out.strip().splitlines()[-12:]))


# In-process checks on the rules this skill shares with edit, publish and magazine.
def _load_audit():
    spec = importlib.util.spec_from_file_location("_selftest_audit", AUDIT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load_audit()
FENCES = HERE / "fences"
BUILDER = HERE.parents[1] / "magazine" / "scripts" / "build-magazine.mjs"


def fences_match_the_shared_answer():
    doc = FENCES / "every-fence.md"
    text = doc.read_text(encoding="utf-8")
    lines = audit.fences.split_lines(text)
    want = json.loads((FENCES / "every-fence.expected.json").read_text(encoding="utf-8"))["fences"]
    got = [{"open": f.start + 1, "close": f.end + 1 if f.end < len(lines) else None, "lang": f.lang, "engine": f.engine}
           for f in audit.fences.scan(text)]
    assert got == want, got
    # and the diagram gate takes exactly the diagram fences from it, in order
    diagrams = [f for f in want if f["engine"]]
    extracted = audit.extract_diagrams(doc)
    assert len(extracted) == len(diagrams), len(extracted)
    for (_, src, _), f in zip(extracted, diagrams):
        assert src.splitlines()[0].strip() == lines[f["open"]].strip(), (src, f)


def presence_matches_the_shared_cases():
    cases = json.loads((HERE / "presence-cases.json").read_text(encoding="utf-8"))["cases"]
    for c in cases:
        t = c["after"]
        assert audit.token_present(c["fact"], audit._tokens(t), t) == c["kept"], c


def magazine_target_renders_as_the_magazine_does():
    """The same figure, measured by the gate for the magazine and placed by the builder, has one
    native size: both render with the magazine's own mermaid config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        run("check", "edges.mmd", "--target", "magazine", "--json", str(tmp / "r.json"))
        rep = json.loads((tmp / "r.json").read_text(encoding="utf-8"))[0]
        doc = tmp / "edges.md"
        doc.write_text("# T\n\n```mermaid\n" + (HERE / "edges.mmd").read_text(encoding="utf-8") + "\n```\n", encoding="utf-8")
        r = subprocess.run(["node", str(BUILDER), "--out", str(tmp / "e.html"), "--kind", "brief", str(doc)],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
        m = re.search(r"native (\d+)x(\d+)", r.stdout)
        assert m, r.stdout + r.stderr
        got = (round(rep["native_w"]), round(rep["native_h"]))
        assert got == (int(m.group(1)), int(m.group(2))), (got, m.group(0))


def tall_figure_measures_what_the_magazine_prints():
    """A figure the magazine shrinks to the page height is measured at that size, not its
    width-only size: the gate and a real build report the same label size, per edition kind."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        doc = tmp / "tall.md"
        doc.write_text("# T\n\n```mermaid\n" + (HERE / "tall.mmd").read_text(encoding="utf-8") + "\n```\n", encoding="utf-8")
        for kind in ("feature", "brief"):
            _, out = run("check", "tall.mmd", "--target", "magazine", "--kind", kind, "--json", str(tmp / "r.json"))
            rep = json.loads((tmp / "r.json").read_text(encoding="utf-8"))[0]
            r = subprocess.run(["node", str(BUILDER), "--out", str(tmp / "t.html"), "--kind", kind, str(doc)],
                               capture_output=True, text=True, encoding="utf-8", timeout=300)
            m = re.search(r"labels (\d+\.\d)pt", r.stdout)
            assert m, r.stdout + r.stderr
            assert f"{rep['label_pt_at_target']:.1f}" == m.group(1), (kind, rep["label_pt_at_target"], m.group(0))
            assert rep["label_pt_at_target"] < 7.0 and "illegible" in out and "placed as" in out, out


def labels_match_the_shared_answer():
    """Every tool reads a figure's title and caption the same way (fences.json figureLabels)."""
    audit = _load_audit()
    want = json.loads((FENCES / "labels.expected.json").read_text(encoding="utf-8"))["labels"]
    got = [{"title": t, "caption": c} for t, c in audit.figure_labels(FENCES / "labels.md")]
    assert got == want, got


def audit_keeps_no_copy_of_the_magazine_page():
    """The magazine's page lives in the builder; a second copy here once measured a tall figure at
    12pt while the edition printed it at 4.2pt. The magazine target has no width of its own."""
    src = AUDIT.read_text(encoding="utf-8")
    for tell in ("geometry.json", "pageIn", "marginIn"):
        assert tell not in src, f"audit.py reads the magazine's page again ({tell})"
    assert _load_audit().TARGETS["magazine"] is None


CHECKS = [
    ("every fence shape gets the shared answer (fences.json, tests/fences)", fences_match_the_shared_answer),
    ("every figure's title and caption get the shared answer (tests/fences/labels)", labels_match_the_shared_answer),
    ("audit.py keeps no copy of the magazine page; the builder places every figure", audit_keeps_no_copy_of_the_magazine_page),
    ("a tall figure measures at the size the magazine prints it, not its width-only size", tall_figure_measures_what_the_magazine_prints),
    ("one presence rule with the edit gate: every shared case gets the same verdict", presence_matches_the_shared_cases),
    ("--target magazine measures with the magazine's own mermaid config", magazine_target_renders_as_the_magazine_does),
]
for name, fn in CHECKS:
    try:
        fn()
        print(f"PASS  {name}")
    except Exception as exc:  # an assertion or a crash is a miss either way
        bad += 1
        print(f"FAIL  {name}\n      {type(exc).__name__}: {str(exc)[:400]}")
total = len(CASES) + len(CHECKS)
print(f"{total - bad}/{total} gate tests pass")
sys.exit(1 if bad else 0)
