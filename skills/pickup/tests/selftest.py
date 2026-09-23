#!/usr/bin/env python3
"""One case per behavior latest.py promises: a malformed banner does not hide the other notes,
a missing --root value does not crash, a git failure is reported (not read as "nothing
changed"), and names compare the same regardless of case or separator. Run:
python tests/selftest.py — expect N/N."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import latest  # noqa: E402

FAILURES_DIR = Path(__file__).resolve().parent / 'failures'
_current_case = ''


@contextmanager
def fixture_dir():
    """A scratch repo/notes tree for one case. Deleted on success; kept under tests/failures/ for
    review when the case's assertion fails, so a red case can be reproduced without re-reading
    the test code to reconstruct its input."""
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


def run(argv) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            code = latest.main(argv)
        except SystemExit as e:  # argparse
            code = int(e.code or 0)
    return code, buf.getvalue()


def init_repo(d: Path) -> None:
    for cmd in (['init', '-q'], ['config', 'user.email', 'test@test'], ['config', 'user.name', 'test']):
        subprocess.run(['git', *cmd], cwd=d, check=True, capture_output=True, timeout=30)


def note(d: Path, subdir: str, filename: str, banner: str, body: str = 'body\n') -> Path:
    p = d / subdir
    p.mkdir(parents=True, exist_ok=True)
    f = p / filename
    f.write_text(banner + '\n\n' + body, encoding='utf-8')
    return f


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case('happy path: a well-formed note round-trips through name, banner and git status')
def _():
    with fixture_dir() as d:
        init_repo(d)
        note(d, 'docs/handoffs', '2026-09-20-doc-pipeline.md', '# Handoff 2026-09-20 14:05 · doc-pipeline')
        code, out = run(['doc-pipeline', '--root', str(d)])
    assert code == 0 and 'resume from' in out and 'commits since' in out and 'dirty now' in out, out


@case('a malformed date in one banner does not hide the other notes')
def _():
    with fixture_dir() as d:
        init_repo(d)
        note(d, 'docs/handoffs', '2026-09-20-good.md', '# Handoff 2026-09-20 14:05 · good')
        note(d, 'docs/handoffs', '2026-02-30-bad.md', '# Handoff 2026-02-30 09:00 · bad')  # Feb 30
        note(d, 'docs/handoffs', '2026-09-21-late.md', '# Handoff 2026-09-21 25:10 · late')  # hour 25
        code, out = run(['--root', str(d)])  # list everything, no name filter
    assert code == 0 and 'good' in out and 'bad' in out and 'late' in out, out


@case('--root with no value is a clean usage error, not a crash')
def _():
    try:
        code, out = run(['--root'])
    except IndexError as e:
        raise AssertionError(f'crashed with IndexError instead of a usage error: {e}')
    assert code == 2, (code, out)


@case('a git failure is reported, never read as "nothing changed"')
def _():
    with fixture_dir() as d:
        # No git init here: git itself fails, and pickup must say so rather than print the same
        # "none" / "clean" a real clean repo would.
        note(d, 'docs/handoffs', '2026-09-20-solo.md', '# Handoff 2026-09-20 14:05 · solo')
        code, out = run(['--root', str(d)])
    assert code == 0, out
    assert out.count('git failed') == 2, out
    assert 'none' not in out.split('commits since')[1].split('dirty now')[0], out
    assert 'clean' not in out.split('dirty now')[1], out


@case('names compare the same regardless of case or separator')
def _():
    with fixture_dir() as d:
        init_repo(d)
        # Banner says "Doc Pipeline"; the file itself is named with hyphens, lowercase — the
        # shape a sibling session's file-only slug would take.
        note(d, 'docs/handoffs', '2026-09-19-doc-pipeline.md', '# Handoff 2026-09-19 09:00 · Doc Pipeline')
        note(d, '.claude/checkpoints', '2026-09-20-doc-pipeline.md', '# Checkpoint 2026-09-20 10:00')
        code, out = run(['doc-pipeline', '--root', str(d)])
    assert code == 0 and 'no note named' not in out, out
    assert out.count('doc-pipeline') >= 2, out


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
