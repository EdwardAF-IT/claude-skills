#!/usr/bin/env python3
"""The publish board: run every stage's mechanical gate over one document and say, per stage,
green or not — and for each finding, which stage it goes back to.

    publish.py board <doc.md> [--before <before.md>] [--kind feature|brief|dashboard]
                              [--out <edition.html>] [--no-build] [--json out.json]

Stages, in order, each with the gate it already owns:
    0 write     the author (no mechanical gate; receives tickets from every later stage)
    1 diagram   ~/.claude/skills/diagram/scripts/audit.py check --target magazine
    2 edit      ~/.claude/skills/edit/scripts/prose_audit.py check (+ diff when --before is given)
    3 magazine  ~/.claude/skills/magazine/scripts/build-magazine.mjs (fidelity gate, plate sizes)

A ticket is (from-stage, to-stage, what, where). Tickets only go backwards. The board does the
mechanical half; the judgement half (the cold reader's meaning list, the art director's eye) is
the agents' and lands in the same shape by hand. Exit 0 when every stage is green, else 1.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')

HOME = Path(os.path.expanduser('~'))
DIAGRAM_AUDIT = HOME / '.claude' / 'skills' / 'diagram' / 'scripts' / 'audit.py'
PROSE_AUDIT = HOME / '.claude' / 'skills' / 'edit' / 'scripts' / 'prose_audit.py'
MAGAZINE_BUILD = HOME / '.claude' / 'skills' / 'magazine' / 'scripts' / 'build-magazine.mjs'

STAGES = ['write', 'diagram', 'edit', 'magazine']


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


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or '')


# ---------------------------------------------------------------- stage 1: diagram

def stage_diagram(doc: Path) -> StageResult:
    if not DIAGRAM_AUDIT.exists():
        return StageResult('diagram', False, 'audit.py not found', [Ticket('diagram', 'diagram', f'missing {DIAGRAM_AUDIT}')])
    code, out = run([sys.executable, str(DIAGRAM_AUDIT), 'check', str(doc), '--target', 'magazine'])
    tickets: list[Ticket] = []
    figure = None
    for line in out.splitlines():
        m = re.match(r'^(\S+#\d+)\s', line)
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
    figures = len(re.findall(r'^\S+#\d+\s', out, re.M))
    blockers = sum(1 for t in tickets)
    green = code == 0 or (code == 1 and not blockers)
    return StageResult('diagram', green, f'{figures} figure(s), {blockers} blocker(s), audit exit {code}', tickets, out)


# ---------------------------------------------------------------- stage 2: edit

def stage_edit(doc: Path, before: Path | None) -> StageResult:
    if not PROSE_AUDIT.exists():
        return StageResult('edit', False, 'prose_audit.py not found', [Ticket('edit', 'edit', f'missing {PROSE_AUDIT}')])
    code, out = run([sys.executable, '-W', 'ignore', str(PROSE_AUDIT), 'check', str(doc)])
    tickets: list[Ticket] = []
    head = out.splitlines()[0] if out else ''
    walls = re.findall(r'^\s*\[wall\]\s+(.*)$', out, re.M)
    longs = re.findall(r'^\s*\[long\]\s+line (\d+): (\d+)w', out, re.M)
    very_long = [(ln, n) for ln, n in longs if int(n) > 45]
    for w in walls:
        tickets.append(Ticket('edit', 'edit', f'wall: {w}'))
    for ln, n in very_long:
        tickets.append(Ticket('edit', 'edit', f'{n}-word sentence', f'line {ln}'))
    summary = head.split(': ', 1)[1] if ': ' in head else head
    if before is not None:
        dcode, dout = run([sys.executable, '-W', 'ignore', str(PROSE_AUDIT), 'diff', str(before), str(doc)])
        for m in re.finditer(r'^\s*\[DESTROYED\]\s+(.*)$', dout, re.M):
            tickets.append(Ticket('edit', 'edit', f'DESTROYED: {m.group(1)[:140]}'))
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
    if not MAGAZINE_BUILD.exists():
        return StageResult('magazine', False, 'build-magazine.mjs not found', [Ticket('magazine', 'magazine', f'missing {MAGAZINE_BUILD}')])
    cmd = ['node', str(MAGAZINE_BUILD), '--out', str(out_path), '--kicker', 'Design']
    if kind:
        cmd += ['--kind', kind]
    cmd.append(str(doc))
    code, out = run(cmd)
    tickets: list[Ticket] = []
    for m in re.finditer(r'WARNING figure (\d+): labels print at ([\d.]+)pt', out):
        tickets.append(Ticket('magazine', 'diagram', f'labels print at {m.group(2)}pt (floor 7)', f'figure {m.group(1)}'))
    if code != 0:
        missing = re.findall(r'^\s+line \d+:.*$', out, re.M)
        tickets.append(Ticket('magazine', 'magazine', 'build failed: ' + (out.strip().splitlines()[-1][:160] if out.strip() else f'exit {code}')))
        for line in missing[:5]:
            tickets.append(Ticket('magazine', 'magazine', 'fidelity: ' + line.strip()[:140]))
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
        stage_diagram(doc),
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
