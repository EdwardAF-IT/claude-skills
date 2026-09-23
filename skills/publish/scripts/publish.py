#!/usr/bin/env python3
"""The publish board: run every stage's mechanical gate over one document and say, per stage,
green or not — and for each finding, which stage it goes back to.

    publish.py board <doc.md> [--before <before.md>] [--kind feature|brief|dashboard]
                              [--out <edition.html>] [--no-build] [--json out.json]

Stages, in order, each with the gate it already owns:
    0 write     the author (no mechanical gate; receives tickets from every later stage)
    1 diagram   ~/.claude/skills/diagram/scripts/audit.py check --target magazine
                (+ diff against --before, which owns fence-level fidelity for stage 1)
    2 edit      ~/.claude/skills/edit/scripts/prose_audit.py check (+ diff when --before is given)
    3 magazine  ~/.claude/skills/magazine/scripts/build-magazine.mjs (fidelity gate, plate sizes)

A ticket is (from-stage, to-stage, what, where). Tickets only go backwards. The board does the
mechanical half; the judgement half (the cold reader's meaning list, the art director's eye) is
the agents' and lands in the same shape by hand.

A stage's verdict comes from its tool's exit code first, never from whether a line happened to
parse: an exit code outside that tool's documented contract, or a traceback in its output, is
red regardless of what the regexes below found. Exit 0 when every stage is green, else 1.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')

# Siblings are resolved from this file's own location, not a hard-coded ~/.claude, so a
# publish.py run inside a clone (or an install to a non-default ClaudeHome) finds the tools it
# ships beside rather than silently falling back to whatever happens to be installed.
SKILLS_DIR = Path(__file__).resolve().parents[2]
DIAGRAM_AUDIT = SKILLS_DIR / 'diagram' / 'scripts' / 'audit.py'
PROSE_AUDIT = SKILLS_DIR / 'edit' / 'scripts' / 'prose_audit.py'
MAGAZINE_BUILD = SKILLS_DIR / 'magazine' / 'scripts' / 'build-magazine.mjs'

STAGES = ['write', 'diagram', 'edit', 'magazine']

RUN_TIMEOUT = 300  # seconds; generous for an mmdc-heavy magazine build. A hang is a red stage,
                    # never a wedged board.


def _load_const(path: Path, name: str, default):
    """Read a threshold straight from the tool that owns it, so publish.py cannot drift from a
    number the tool itself changed. A missing tool falls back to `default` (its stage goes red on
    its own); a tool that exists but will not load, or lacks the name, is an error — a silent
    default here once hid that audit.py had never loaded at all."""
    if not path.exists():
        return default
    mod_name = f'_publish_const_{path.stem}'
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    # Registered before running: dataclasses look their module up in sys.modules while loading.
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, name)


VERY_LONG_SENTENCE = _load_const(PROSE_AUDIT, 'VERY_LONG_SENTENCE', 45)
LABEL_FLOOR_PT = _load_const(DIAGRAM_AUDIT, 'LABEL_FLOOR_PT', 7.0)
# build-magazine.mjs has no Python module to import from; its own labelFloorPt (build-magazine.mjs:977)
# is meant to equal the diagram gate's LABEL_FLOOR_PT above — named here, not re-guessed.


@dataclass
class Ticket:
    from_stage: str
    to_stage: str
    what: str
    where: str = ''


@dataclass
class StageResult:
    stage: str
    green: bool
    summary: str
    tickets: list[Ticket]
    output: str = ''


def run(cmd: list[str], cwd: Path | None = None, timeout: float = RUN_TIMEOUT) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or '') + (e.stderr or '')
        return 124, out + f'\n[publish] timed out after {timeout}s'
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def _tail(out: str, n: int = 6) -> str:
    """The last few non-blank lines of a tool's combined stdout/stderr — enough to see why a
    crashed gate crashed without dumping the whole traceback into the board."""
    lines = [line for line in out.splitlines() if line.strip()]
    return '\n'.join(lines[-n:])


def _crashed(code: int, out: str, ok_codes: tuple[int, ...]) -> bool:
    """True when a gate's exit code falls outside its own documented contract, or its output
    carries a traceback — the two ways a gate reports "green" without having judged anything."""
    return code not in ok_codes or 'Traceback (most recent call last):' in out


def _require_tool(stage: str, tool: Path) -> StageResult | None:
    """The existence check every stage opens with: red with a ticket to itself if its tool is
    missing, else None so the caller proceeds."""
    if tool.exists():
        return None
    return StageResult(stage, False, f'{tool.name} not found', [Ticket(stage, stage, f'missing {tool}')])


# ---------------------------------------------------------------- stage 1: diagram

def stage_diagram(doc: Path, before: Path | None) -> StageResult:
    missing = _require_tool('diagram', DIAGRAM_AUDIT)
    if missing:
        return missing
    code, out = run([sys.executable, str(DIAGRAM_AUDIT), 'check', str(doc), '--target', 'magazine'])
    if _crashed(code, out, (0, 1, 2)):
        return StageResult('diagram', False, f'audit.py check crashed, exit {code}',
                            [Ticket('diagram', 'diagram', f'audit.py check crashed: {_tail(out)}')], out)
    tickets: list[Ticket] = []
    figure = None
    for line in out.splitlines():
        # The figure header is "<name>#<index>  <kind>/<direction> ...": two spaces after the
        # index, so a document name that itself contains a space (".+", not "\S+") still matches.
        m = re.match(r'^(.+#\d+)(?=\s\s)', line)
        if m:
            figure = m.group(1)
            continue
        f = re.match(r'^\s*\[(blocker|warning)\]\s+([a-z-]+):\s*(.*)$', line)
        if not f:
            continue
        level, kind, text = f.groups()
        # What needs the author, not a redraw: a figure whose participants or entities make it
        # illegible at any width, or one the tool cannot parse to verify.
        if kind in ('needs-author',):
            tickets.append(Ticket('diagram', 'write', f'{kind}: {text[:140]}', figure or ''))
        elif level == 'blocker':
            tickets.append(Ticket('diagram', 'diagram', f'{kind}: {text[:140]}', figure or ''))
    if code == 2 and not any(t.to_stage == 'diagram' for t in tickets):
        # The gate itself says blocker (exit 2); if no blocker line parsed, the parser drifted
        # from the tool's own wording — that is still red, not a silent pass.
        tickets.append(Ticket('diagram', 'diagram', f'audit.py check exited blocker (2) with no parsed blocker: {_tail(out)}'))
    figures = len(re.findall(r'^.+#\d+\s\s', out, re.M))
    summary = f'{figures} figure(s), {sum(1 for t in tickets if t.to_stage == "diagram")} blocker(s), audit exit {code}'
    if before is not None and (figures > 0 or _has_diagram_fence(before)):
        # The diagram diff, not the prose diff, owns diagram fences: it is the one gate that can
        # tell a legitimate redraw (IDENTICAL entities) from a lossy one (a dropped node or edge).
        # It runs whenever either side has a diagram, so deleting every diagram is red, not
        # skipped; a prose-only document on both sides has nothing to diff.
        dcode, dout = run([sys.executable, str(DIAGRAM_AUDIT), 'diff', str(before), str(doc)])
        if _crashed(dcode, dout, (0, 1, 2, 3)):
            tickets.append(Ticket('diagram', 'diagram', f'audit.py diff crashed: {_tail(dout)}'))
        else:
            verdict = re.search(r'^VERDICT: \w+[^\n]*', dout, re.M)
            summary += ' | redraw: ' + (verdict.group(0) if verdict else f'exit {dcode}')
            if dcode != 0:
                found = False
                for m in re.finditer(r'^(entities removed|relationships removed)\s*:\s*(.*)$', dout, re.M):
                    if m.group(2).strip() != '-':
                        tickets.append(Ticket('diagram', 'diagram', f'redraw dropped {m.group(1)}: {m.group(2)[:140]}'))
                        found = True
                if not found:
                    tail = verdict.group(0) if verdict else dout.strip().splitlines()[-1][:140]
                    tickets.append(Ticket('diagram', 'diagram', f'redraw diff not IDENTICAL: {tail[:160]}'))
        out += '\n' + dout
    green = not tickets
    return StageResult('diagram', green, summary, tickets, out)


FENCES = SKILLS_DIR / 'diagram' / 'scripts' / 'fences.py'


def _fences():
    """The diagram skill's fence definition — the one every stage reads — loaded by path. Called
    only after a gate that itself needs the diagram skill has run."""
    key = '_diagram_fences'
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, FENCES)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod    # registered first: a dataclass module needs itself in sys.modules
        spec.loader.exec_module(mod)
    return sys.modules[key]


def _has_diagram_fence(path: Path) -> bool:
    return any(f.diagram for f in _fences().scan(path.read_text(encoding='utf-8', errors='replace')))


def _is_diagram_fence_loss(destroyed: str) -> bool:
    # prose_audit prints a lost fence as: fence '<lang> fence' (line N) ...
    m = re.match(r"fence '(\S+) fence'", destroyed)
    return bool(m) and m.group(1).lower() in _fences().DIAGRAM_LANGS


# ---------------------------------------------------------------- stage 2: edit

def stage_edit(doc: Path, before: Path | None) -> StageResult:
    missing = _require_tool('edit', PROSE_AUDIT)
    if missing:
        return missing
    code, out = run([sys.executable, '-W', 'ignore', str(PROSE_AUDIT), 'check', str(doc)])
    if _crashed(code, out, (0,)):
        return StageResult('edit', False, f'prose_audit.py check crashed, exit {code}',
                            [Ticket('edit', 'edit', f'prose_audit.py check crashed: {_tail(out)}')], out)
    tickets: list[Ticket] = []
    head = out.splitlines()[0] if out else ''
    walls = re.findall(r'^\s*\[wall\]\s+(.*)$', out, re.M)
    longs = re.findall(r'^\s*\[long\]\s+line (\d+): (\d+)w', out, re.M)
    very_long = [(ln, n) for ln, n in longs if int(n) > VERY_LONG_SENTENCE]
    for w in walls:
        tickets.append(Ticket('edit', 'edit', f'wall: {w}'))
    for ln, n in very_long:
        tickets.append(Ticket('edit', 'edit', f'{n}-word sentence', f'line {ln}'))
    summary = head.split(': ', 1)[1] if ': ' in head else head
    if before is not None:
        dcode, dout = run([sys.executable, '-W', 'ignore', str(PROSE_AUDIT), 'diff', str(before), str(doc)])
        if _crashed(dcode, dout, (0, 1, 2)):
            tickets.append(Ticket('edit', 'edit', f'prose_audit.py diff crashed: {_tail(dout)}'))
        else:
            for m in re.finditer(r'^\s*\[DESTROYED\]\s+(.*)$', dout, re.M):
                text = m.group(1)
                if _is_diagram_fence_loss(text):
                    # Diagram fences are stage 1's asset: the diagram diff gates them against the
                    # same before, so a redraw doesn't also land here. Any other fence (a code
                    # sample) is prose content and stays this stage's ticket.
                    continue
                tickets.append(Ticket('edit', 'edit', f'DESTROYED: {text[:140]}'))
            for m in re.finditer(r'^\s*\[causal\]\s+(.*)$', dout, re.M):
                tickets.append(Ticket('edit', 'edit', f'causal: {m.group(1)[:140]}'))
            for m in re.finditer(r'^\s*\[changed\]\s+(.*)$', dout, re.M):
                tickets.append(Ticket('edit', 'edit', f'changed (declare it): {m.group(1)[:140]}'))
        verdict = re.search(r'^(KEPT|CHANGED|DESTROYED|CAUSAL)[^\n]*', dout, re.M)
        summary += ' | gate: ' + (verdict.group(0) if verdict else f'exit {dcode}')
        out += '\n' + dout
    green = not tickets
    return StageResult('edit', green, summary, tickets, out)


# ---------------------------------------------------------------- stage 3: magazine

def stage_magazine(doc: Path, out_path: Path, kind: str | None, build: bool) -> StageResult:
    if not build:
        return StageResult('magazine', True, 'skipped (--no-build)', [])
    missing = _require_tool('magazine', MAGAZINE_BUILD)
    if missing:
        return missing
    cmd = ['node', str(MAGAZINE_BUILD), '--out', str(out_path), '--kicker', 'Design']
    if kind:
        cmd += ['--kind', kind]
    cmd.append(str(doc))
    code, out = run(cmd)
    if _crashed(code, out, (0, 2)):
        return StageResult('magazine', False, f'build-magazine.mjs crashed, exit {code}',
                            [Ticket('magazine', 'magazine', f'build-magazine.mjs crashed: {_tail(out)}')], out)
    tickets: list[Ticket] = []
    for m in re.finditer(r'WARNING figure (\d+): labels print at ([\d.]+)pt', out):
        tickets.append(Ticket('magazine', 'diagram', f'labels print at {m.group(2)}pt (floor {LABEL_FLOOR_PT:g})', f'figure {m.group(1)}'))
    if code != 0:
        # Matches what build-magazine.mjs actually prints: "build-magazine: MISSING <file>:<line>: <text>".
        for m in re.finditer(r'^build-magazine: MISSING (\S+):(\d+): (.*)$', out, re.M):
            tickets.append(Ticket('magazine', 'magazine', f'fidelity: {m.group(1)}:{m.group(2)}: {m.group(3)[:140]}'))
        if not tickets:
            tickets.append(Ticket('magazine', 'magazine', 'build failed: ' + (out.strip().splitlines()[-1][:160] if out.strip() else f'exit {code}')))
    kind_line = re.search(r'^kind: [^\n]*', out, re.M)
    fid = 'fidelity ok' if 'fidelity: every source line' in out else 'fidelity NOT proven'
    summary = (kind_line.group(0) if kind_line else '') + ' | ' + fid
    green = code == 0 and not tickets
    return StageResult('magazine', green, summary, tickets, out)


# ---------------------------------------------------------------- the board

def print_board(doc: Path, results: list[StageResult]) -> None:
    print(f'publish board: {doc}')
    for r in results:
        mark = 'green' if r.green else 'RED  '
        print(f'  [{mark}] {r.stage:<9} {r.summary}')
    back = [t for r in results for t in r.tickets]
    if not back:
        print('  every stage green')
        return
    print(f'  {len(back)} ticket(s):')
    for t in back:
        where = f' ({t.where})' if t.where else ''
        print(f'    {t.from_stage} -> {t.to_stage}: {t.what}{where}')
    to_write = [t for t in back if t.to_stage == 'write']
    if to_write:
        print(f'  {len(to_write)} of them go back to the author: they need a fact the document does not carry')


def cmd_board(args) -> int:
    doc = Path(args.doc).resolve()
    before = Path(args.before).resolve() if args.before else None
    out_path = Path(args.out).resolve() if args.out else doc.with_name(doc.stem + '-print.html')
    results = [
        stage_diagram(doc, before),
        stage_edit(doc, before),
        stage_magazine(doc, out_path, args.kind, build=not args.no_build),
    ]
    print_board(doc, results)
    if args.json:
        Path(args.json).write_text(json.dumps([{**asdict(r), 'tickets': [asdict(t) for t in r.tickets]} for r in results], indent=2), encoding='utf-8')
        print(f'  wrote {args.json}')
    if args.verbose:
        for r in results:
            print(f'\n===== {r.stage}\n{r.output}')
    return 0 if all(r.green for r in results) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('board')
    b.add_argument('doc')
    b.add_argument('--before')
    b.add_argument('--kind', choices=['feature', 'brief', 'dashboard'])
    b.add_argument('--out')
    b.add_argument('--no-build', action='store_true')
    b.add_argument('--json')
    b.add_argument('--verbose', action='store_true')
    b.set_defaults(fn=cmd_board)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
