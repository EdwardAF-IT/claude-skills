#!/usr/bin/env python3
"""One case per finding this test guards. Each fixture fails without the fix it proves; a gate
suite that cannot go red is decoration. Run: python selftest.py — from any directory, expect
N/N.

Finds publish.py and its own fixtures relative to this file, never ~/.claude/skills, so it
proves the repo's own copy, not whatever happens to be installed on this box."""
from __future__ import annotations

import importlib.util
import io
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / 'fixtures'
PUBLISH_PY = HERE.parent / 'scripts' / 'publish.py'
FAILURES_DIR = HERE / 'failures'

sys.path.insert(0, str(PUBLISH_PY.parent))
import publish as pub  # noqa: E402

_current_case = ''


@contextmanager
def fixture_dir():
    """A scratch directory for one case's own fixtures. Deleted on success; kept under
    tests/failures/ for review when the case's assertion fails."""
    d = Path(tempfile.mkdtemp())
    try:
        yield d
    except BaseException:
        name = re.sub(r'[^a-z0-9]+', '-', _current_case.lower()).strip('-')[:80] or 'case'
        dest = FAILURES_DIR / name
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(d, dest)
        raise
    finally:
        shutil.rmtree(d, ignore_errors=True)


CASES: list[tuple[str, callable]] = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def run_cli(*args: str) -> tuple[int, str]:
    """The production entry point: the actual `python publish.py board ...` a caller runs, not
    a shortcut through the module's functions."""
    p = subprocess.run([sys.executable, str(PUBLISH_PY), *args], capture_output=True, text=True,
                        timeout=180)
    return p.returncode, p.stdout + p.stderr


def board_via_module(doc: Path, before: Path | None = None, no_build: bool = True) -> tuple[int, str]:
    """Drives publish.py's own cmd_board with the module's current (possibly monkeypatched)
    DIAGRAM_AUDIT/PROSE_AUDIT/MAGAZINE_BUILD, for cases that stub a sibling tool to force a
    specific exit code deterministically."""
    class Args:
        pass
    args = Args()
    args.doc = str(doc)
    args.before = str(before) if before else None
    args.kind = None
    args.out = None
    args.no_build = no_build
    args.json = None
    args.verbose = False
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = pub.cmd_board(args)
    return code, buf.getvalue()


# ---------------------------------------------------------------- real audit.py / prose_audit.py

@case('a missing document is red, not "every stage green" (finding 2)')
def _():
    code, out = run_cli('board', str(FIXTURES / 'does-not-exist.md'), '--no-build')
    assert code != 0, out
    assert 'every stage green' not in out, out


@case('a legitimate diagram redraw (TD -> LR, same graph) is diagram green (finding 3)')
def _():
    code, out = run_cli('board', str(FIXTURES / 'diag-after-legit.md'),
                         '--before', str(FIXTURES / 'diag-before.md'), '--no-build')
    assert '[green] diagram' in out, out
    assert 'edit -> edit: DESTROYED' not in out, out  # fence facts stay diagram's, not edit's


@case('a redraw that drops a node is red with a ticket to diagram, not edit (finding 3)')
def _():
    code, out = run_cli('board', str(FIXTURES / 'diag-after-lossy.md'),
                         '--before', str(FIXTURES / 'diag-before.md'), '--no-build')
    assert code != 0, out
    assert '[RED  ] diagram' in out, out
    assert any(l.strip().startswith('diagram -> diagram: redraw dropped') for l in out.splitlines()), out
    assert not any(l.strip().startswith('edit -> edit:') for l in out.splitlines()), out


@case('deleting every diagram is red, not skipped because the after has no figures')
def _():
    code, out = run_cli('board', str(FIXTURES / 'diag-after-deleted.md'),
                         '--before', str(FIXTURES / 'diag-before.md'), '--no-build')
    assert code != 0, out
    assert '[RED  ] diagram' in out, out


@case('a deleted code sample stays an edit ticket; only diagram fences belong to stage 1')
def _():
    code, out = run_cli('board', str(FIXTURES / 'code-after-deleted.md'),
                         '--before', str(FIXTURES / 'code-before.md'), '--no-build')
    assert code != 0, out
    assert '[RED  ] edit' in out, out
    assert 'python fence' in out, out


@case('a document with no diagram at all does not get a false diagram ticket (finding 3)')
def _():
    code, out = run_cli('board', str(FIXTURES / 'prose-after-lossy.md'),
                         '--before', str(FIXTURES / 'prose-before.md'), '--no-build')
    assert '[green] diagram' in out, out  # UNVERIFIABLE with 0 figures is not a redraw defect


@case('a dropped fact (non-fence) in prose is an edit refusal: red, ticket to edit')
def _():
    code, out = run_cli('board', str(FIXTURES / 'prose-after-lossy.md'),
                         '--before', str(FIXTURES / 'prose-before.md'), '--no-build')
    assert code != 0, out
    assert '[RED  ] edit' in out, out
    assert 'edit -> edit: DESTROYED' in out, out


@case('a document name with a space is parsed as one figure, not lost (finding 4)')
def _():
    doc = FIXTURES / 'a doc with spaces.md'
    code, out = run_cli('board', str(doc), '--no-build')
    assert code == 0, out
    assert '1 figure(s)' in out, out


@case('the old figure regex would have missed the space (regression guard for finding 4)')
def _():
    line = 'a doc with spaces.md#0  flowchart/TD  nodes=2 edges=1  labels<=3w=yes edges<=3w=yes pt@target=8.0'
    old = re.match(r'^(\S+#\d+)\s', line)
    new = re.match(r'^(.+#\d+)(?=\s\s)', line)
    assert old is None, 'old pattern unexpectedly matched — fixture no longer demonstrates the bug'
    assert new is not None and new.group(1) == 'a doc with spaces.md#0', new


@case('the happy path: a clean document with no --before is every-stage green (real tools)')
def _():
    code, out = run_cli('board', str(FIXTURES / 'happy.md'), '--no-build')
    assert code == 0, out
    assert 'every stage green' in out, out


# ---------------------------------------------------------------- stubbed sibling tools

@case('a gate that crashes with a traceback is red, board exits nonzero (finding 2)')
def _():
    saved = pub.DIAGRAM_AUDIT
    pub.DIAGRAM_AUDIT = FIXTURES / 'stub-audit-crash.py'
    # stub is a .py; publish.py invokes it with sys.executable, so no shebang/exec-bit needed.
    try:
        with fixture_dir() as d:
            doc = Path(d) / 'doc.md'
            doc.write_text('# T\n\nBody.\n', encoding='utf-8')
            code, out = board_via_module(doc)
    finally:
        pub.DIAGRAM_AUDIT = saved
    assert code != 0, out
    assert 'every stage green' not in out, out
    assert '[RED  ] diagram' in out, out


@case('an exit code outside the documented contract is red even with no "Traceback" text (finding 2)')
def _():
    saved = pub.PROSE_AUDIT
    pub.PROSE_AUDIT = FIXTURES / 'stub-prose-audit-undocumented-exit.py'
    try:
        with fixture_dir() as d:
            doc = Path(d) / 'doc.md'
            doc.write_text('# T\n\nBody.\n', encoding='utf-8')
            r = pub.stage_edit(doc, None)
    finally:
        pub.PROSE_AUDIT = saved
    assert r.green is False
    assert any(t.to_stage == 'edit' for t in r.tickets), r.tickets


@case('a missing sibling tool is its own red ticket, not a crash (finding 6 / _require_tool)')
def _():
    saved = pub.DIAGRAM_AUDIT
    pub.DIAGRAM_AUDIT = FIXTURES / 'does-not-exist-audit.py'
    try:
        r = pub.stage_diagram(FIXTURES / 'happy.md', None)
    finally:
        pub.DIAGRAM_AUDIT = saved
    assert r.green is False
    assert 'not found' in r.summary
    assert r.tickets and r.tickets[0].from_stage == 'diagram' and r.tickets[0].to_stage == 'diagram'


@case('a magazine fidelity failure matches the real MISSING line and tickets to magazine (finding 5)')
def _():
    saved = pub.MAGAZINE_BUILD
    pub.MAGAZINE_BUILD = FIXTURES / 'stub-build-missing.mjs'
    try:
        r = pub.stage_magazine(FIXTURES / 'happy.md', Path('out.html'), None, True)
    finally:
        pub.MAGAZINE_BUILD = saved
    assert r.green is False
    assert any('fidelity: doc.md:3:' in t.what for t in r.tickets), r.tickets


@case('a magazine label-floor warning tickets to diagram, using the shared LABEL_FLOOR_PT (finding 5)')
def _():
    saved = pub.MAGAZINE_BUILD
    pub.MAGAZINE_BUILD = FIXTURES / 'stub-build-warn.mjs'
    try:
        r = pub.stage_magazine(FIXTURES / 'happy.md', Path('out.html'), None, True)
    finally:
        pub.MAGAZINE_BUILD = saved
    assert r.green is False
    assert len(r.tickets) == 1 and r.tickets[0].to_stage == 'diagram'
    assert f'floor {pub.LABEL_FLOOR_PT:g}' in r.tickets[0].what, r.tickets[0]


@case('a magazine crash outside its own try/catch is still red (finding 2)')
def _():
    saved = pub.MAGAZINE_BUILD
    pub.MAGAZINE_BUILD = FIXTURES / 'stub-build-crash.mjs'
    try:
        r = pub.stage_magazine(FIXTURES / 'happy.md', Path('out.html'), None, True)
    finally:
        pub.MAGAZINE_BUILD = saved
    assert r.green is False
    assert r.tickets and r.tickets[0].to_stage == 'magazine'


@case('thresholds are read from the owning tool, not a stale private copy (finding 5)')
def _():
    # A sentinel default, so a silent fallback cannot pass for a real load (7.0 once did).
    sentinel = object()
    assert pub._load_const(pub.PROSE_AUDIT, 'VERY_LONG_SENTENCE', sentinel) is not sentinel
    assert pub._load_const(pub.DIAGRAM_AUDIT, 'LABEL_FLOOR_PT', sentinel) is not sentinel
    assert pub.VERY_LONG_SENTENCE == pub._load_const(pub.PROSE_AUDIT, 'VERY_LONG_SENTENCE', sentinel)
    assert pub.LABEL_FLOOR_PT == pub._load_const(pub.DIAGRAM_AUDIT, 'LABEL_FLOOR_PT', sentinel)


@case('sibling tools resolve relative to publish.py, not a hard-coded ~/.claude/skills (finding 9)')
def _():
    assert pub.DIAGRAM_AUDIT == pub.SKILLS_DIR / 'diagram' / 'scripts' / 'audit.py'
    assert pub.PROSE_AUDIT == pub.SKILLS_DIR / 'edit' / 'scripts' / 'prose_audit.py'
    assert pub.MAGAZINE_BUILD == pub.SKILLS_DIR / 'magazine' / 'scripts' / 'build-magazine.mjs'
    assert pub.SKILLS_DIR == PUBLISH_PY.resolve().parents[2]


SHARED_FENCES = HERE.parents[1] / 'diagram' / 'tests' / 'fences'


@case('the board agrees with every other tool on what a diagram fence is (shared fixture, finding 10)')
def _():
    import json
    doc = (SHARED_FENCES / 'every-fence.md').read_text(encoding='utf-8')
    want = json.loads((SHARED_FENCES / 'every-fence.expected.json').read_text(encoding='utf-8'))['fences']
    lines = doc.split('\n')
    with fixture_dir() as d:
        for f in want:
            # each fence alone in its own document: the board sees a diagram exactly when the
            # shared answer names an engine (~~~, ::: and Graphviz fences included)
            end = f['close'] if f['close'] else len(lines)
            one = d / f"fence-{f['open']}.md"
            one.write_text('\n'.join(lines[f['open'] - 1:end]) + '\n', encoding='utf-8')
            assert pub._has_diagram_fence(one) == bool(f['engine']), f
            if f['lang']:
                assert pub._is_diagram_fence_loss(f"fence '{f['lang']} fence' (line {f['open']})") == bool(f['engine']), f
        note = d / 'admonition.md'
        note.write_text('::: note\nprose\n:::\n', encoding='utf-8')
        assert not pub._has_diagram_fence(note)


def main() -> int:
    global _current_case
    shutil.rmtree(FAILURES_DIR, ignore_errors=True)
    passed = 0
    for name, fn in CASES:
        _current_case = name
        try:
            fn()
            passed += 1
            print(f'  ok   {name}')
        except AssertionError as e:
            print(f'  FAIL {name}\n       {str(e)[:400]}')
        except Exception as e:  # noqa: BLE001
            print(f'  FAIL {name}\n       {type(e).__name__}: {e}')
    print(f'{passed}/{len(CASES)}')
    return 0 if passed == len(CASES) else 1


if __name__ == '__main__':
    sys.exit(main())
