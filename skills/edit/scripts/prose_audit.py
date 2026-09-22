#!/usr/bin/env python3
"""Measure the reading cost of markdown prose, rank the queue, and gate an edit.

    prose_audit.py audit <path> [--json out.json] [--exclude glob ...]
        Every .md under <path> (or the one file): per-section reading cost, ranked worst first.
    prose_audit.py check <file> [--section "heading"]
        One document's sections in source order, with the walls and the worst sentences named.
    prose_audit.py diff <before.md> <after.md> [--declare "<reason>"]
        The fidelity gate. Every piece of content that carries a fact in the before must be
        present in the after: code spans, identifiers, paths, flags, numbers, cross-references,
        links, headings, table cells, and every fenced block byte for byte. Exit 0 kept, 1 changed
        (a heading or table cell gone), 2 DESTROYED (a fact gone), 3 unverifiable.

The measures are the ones an editor would take by hand, made cheap: words per sentence, the
share of long sentences, words per paragraph, walls (body text with no entry point for 300+
words), identifiers per hundred words, parentheticals per sentence, passive share, and a
reading grade. None is a verdict on its own; together they rank where a reader pays most.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Headings carry arrows and section signs; a cp1252 console must not be the thing that fails.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, 'reconfigure'):
        _stream.reconfigure(encoding='utf-8', errors='replace')

# ---------------------------------------------------------------- thresholds

LONG_SENTENCE = 30          # words; the share of these is the first number an editor looks at
VERY_LONG_SENTENCE = 45
LONG_PARAGRAPH = 120        # words; a paragraph past this is two ideas
WALL_WORDS = 300            # body words with no heading, list, table, figure or quote between
DENSE_CODE = 8              # code spans per hundred words: the prose is a reference, not an argument
EXAMPLE_NUMBER_DIGITS = 4   # a bare number this long is an example value: reported, never a blocker

# ---------------------------------------------------------------- markdown reading

FENCE_RE = re.compile(r'^\s*(```+|~~~+)\s*(\S*)\s*$')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
LIST_RE = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+')
TABLE_RE = re.compile(r'^\s*\|')
QUOTE_RE = re.compile(r'^\s*>')
HR_RE = re.compile(r'^\s*([-*_])\1{2,}\s*$')
COMMENT_RE = re.compile(r'^\s*<!--.*-->\s*$')


@dataclass
class Block:
    kind: str            # heading | p | list | table | fence | quote | hr
    text: str
    line: int
    level: int = 0       # heading level
    lang: str = ''       # fence language


def parse(md: str) -> list[Block]:
    """A flat block list. Lists and tables are one block each; a paragraph is its own block."""
    lines = md.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    blocks: list[Block] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip() or COMMENT_RE.match(line):
            i += 1
            continue
        f = FENCE_RE.match(line)
        if f:
            start = i
            lang = f.group(2)
            i += 1
            while i < n and not re.match(r'^\s*' + re.escape(f.group(1)[0]) + r'{3,}\s*$', lines[i]):
                i += 1
            body = '\n'.join(lines[start + 1:i])
            blocks.append(Block('fence', body, start + 1, lang=lang))
            i += 1
            continue
        h = HEADING_RE.match(line)
        if h:
            blocks.append(Block('heading', h.group(2), i + 1, level=len(h.group(1))))
            i += 1
            continue
        if HR_RE.match(line):
            blocks.append(Block('hr', '', i + 1))
            i += 1
            continue
        if TABLE_RE.match(line):
            start = i
            while i < n and TABLE_RE.match(lines[i]):
                i += 1
            blocks.append(Block('table', '\n'.join(lines[start:i]), start + 1))
            continue
        if QUOTE_RE.match(line):
            start = i
            while i < n and (QUOTE_RE.match(lines[i]) or (lines[i].strip() and not HEADING_RE.match(lines[i]) and QUOTE_RE.match(lines[i - 1]))):
                i += 1
            blocks.append(Block('quote', '\n'.join(lines[start:i]), start + 1))
            continue
        if LIST_RE.match(line):
            start = i
            i += 1
            while i < n:
                cur = lines[i]
                if not cur.strip():
                    # a blank line ends the list unless the next non-blank line is indented or a list line
                    j = i + 1
                    while j < n and not lines[j].strip():
                        j += 1
                    if j < n and (LIST_RE.match(lines[j]) or (lines[j].startswith('  ') and not FENCE_RE.match(lines[j]))):
                        i = j
                        continue
                    break
                if HEADING_RE.match(cur) or FENCE_RE.match(cur) or TABLE_RE.match(cur) or HR_RE.match(cur):
                    break
                if not (LIST_RE.match(cur) or cur.startswith((' ', '\t'))):
                    break
                i += 1
            blocks.append(Block('list', '\n'.join(lines[start:i]), start + 1))
            continue
        # paragraph: up to the next blank line or structural line
        start = i
        i += 1
        while i < n and lines[i].strip() and not (HEADING_RE.match(lines[i]) or FENCE_RE.match(lines[i]) or TABLE_RE.match(lines[i]) or QUOTE_RE.match(lines[i]) or LIST_RE.match(lines[i]) or HR_RE.match(lines[i])):
            i += 1
        blocks.append(Block('p', ' '.join(l.strip() for l in lines[start:i]), start + 1))
    return blocks


# ---------------------------------------------------------------- text measures

CODE_SPAN_RE = re.compile(r'`([^`\n]+)`')
LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)\s]+)\)')
IMAGE_RE = re.compile(r'!\[([^\]]*)\]\([^)]*\)')


def strip_inline(text: str) -> str:
    """Prose only: code spans become a placeholder word, links their text, emphasis dropped."""
    t = IMAGE_RE.sub(r'\1', text)
    t = CODE_SPAN_RE.sub(' CODE ', t)
    t = LINK_RE.sub(r'\1', t)
    t = re.sub(r'[*_~]{1,3}', '', t)
    t = re.sub(r'^\s*(?:[-*+]|\d+[.)])\s+(\[[ xX]\]\s+)?', '', t, flags=re.M)
    t = re.sub(r'^\s*>\s?', '', t, flags=re.M)
    return t


WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-]*")


def words(text: str) -> int:
    return len(WORD_RE.findall(text))


# A sentence ends at . ! ? followed by space and a capital, a quote, or the end. Abbreviations
# common in these documents are protected so "e.g. the" and "§7.3" do not split.
SENT = chr(0xE000)   # stands in for a full stop that does not end a sentence
ABBREV = ('e.g.', 'i.e.', 'etc.', 'vs.', 'cf.', 'No.', 'Fig.', 'Dr.', 'Mr.', 'Ms.', 'St.')


def sentences(text: str) -> list[str]:
    t = text
    for a in ABBREV:
        t = t.replace(a, a.replace('.', SENT))
    t = re.sub(r'(\d)\.(\d)', lambda m: m.group(1) + SENT + m.group(2), t)
    parts = re.split(r'(?<=[.!?])["’”)]?\s+(?=["“(]?[A-Z0-9])', t)
    out = []
    for p in parts:
        p = p.replace(SENT, '.').strip()
        if words(p) > 0:
            out.append(p)
    return out


def syllables(word: str) -> int:
    w = word.lower()
    w = re.sub(r'[^a-z]', '', w)
    if not w:
        return 1
    if len(w) <= 3:
        return 1
    w = re.sub(r'(?:[^laeiouy]es|ed|[^laeiouy]e)$', '', w)
    w = re.sub(r'^y', '', w)
    groups = re.findall(r'[aeiouy]{1,2}', w)
    return max(1, len(groups))


PASSIVE_RE = re.compile(r"\b(?:is|are|was|were|be|been|being|gets?|got)\s+(?:\w+ly\s+)?(\w+(?:ed|en|t))\b")
NOMINAL_RE = re.compile(r'\b\w+(?:tion|sion|ment|ness|ance|ence|ity)s?\b', re.I)
PAREN_RE = re.compile(r'\([^)]*\)|\s[-—–]\s')
HEDGE_RE = re.compile(r'\b(?:in order to|it is (?:worth|important) (?:noting|to note)|note that|as (?:mentioned|noted|described) (?:above|earlier|below)|the fact that|there (?:is|are) (?:a|an|no|some)\b|which is to say|that is to say|needless to say|as such|in terms of|with respect to|a number of|the majority of|at this point in time|due to the fact that)\b', re.I)


@dataclass
class Measures:
    words: int = 0
    sentences: int = 0
    paragraphs: int = 0
    words_per_sentence: float = 0.0
    long_sentence_share: float = 0.0
    very_long_sentences: int = 0
    longest_sentence: int = 0
    words_per_paragraph: float = 0.0
    long_paragraphs: int = 0
    code_per_100: float = 0.0
    passive_share: float = 0.0
    nominal_per_100: float = 0.0
    parens_per_sentence: float = 0.0
    hedges: int = 0
    grade: float = 0.0
    walls: int = 0
    longest_wall: int = 0
    entry_points: int = 0
    cost: float = 0.0


ITEM_SPLIT_RE = re.compile(r'\n(?=\s*(?:[-*+]|\d+[.)])\s+)')


def prose_units(blocks: list[Block]) -> list[str]:
    """The text a reader reads as prose: paragraphs, and every list item as a paragraph of its
    own (a design document's open questions are list items of a hundred words). The list itself
    still counts as an entry point for the wall rule; its items are measured like any prose."""
    units: list[str] = []
    for b in blocks:
        if b.kind == 'p':
            units.append(b.text)
        elif b.kind == 'list':
            for item in ITEM_SPLIT_RE.split(b.text):
                units.append(' '.join(l.strip() for l in item.split('\n')))
    return units


def measure_prose(paragraphs: list[str]) -> Measures:
    m = Measures()
    all_sentences: list[str] = []
    code_spans = 0
    for p in paragraphs:
        code_spans += len(CODE_SPAN_RE.findall(p))
        clean = strip_inline(p)
        w = words(clean)
        if w == 0:
            continue
        m.paragraphs += 1
        m.words += w
        if w > LONG_PARAGRAPH:
            m.long_paragraphs += 1
        all_sentences.extend(sentences(clean))
    m.sentences = len(all_sentences)
    if not m.words or not m.sentences:
        return m
    lens = [words(s) for s in all_sentences]
    m.words_per_sentence = round(sum(lens) / len(lens), 1)
    m.long_sentence_share = round(sum(1 for l in lens if l > LONG_SENTENCE) / len(lens), 2)
    m.very_long_sentences = sum(1 for l in lens if l > VERY_LONG_SENTENCE)
    m.longest_sentence = max(lens)
    m.words_per_paragraph = round(m.words / m.paragraphs, 1)
    m.code_per_100 = round(100 * code_spans / m.words, 1)
    text = ' '.join(all_sentences)
    m.passive_share = round(len(PASSIVE_RE.findall(text)) / m.sentences, 2)
    m.nominal_per_100 = round(100 * len(NOMINAL_RE.findall(text)) / m.words, 1)
    m.parens_per_sentence = round(len(PAREN_RE.findall(text)) / m.sentences, 2)
    m.hedges = len(HEDGE_RE.findall(text))
    syl = sum(syllables(w) for w in WORD_RE.findall(text) if w != 'CODE')
    m.grade = round(0.39 * (m.words / m.sentences) + 11.8 * (syl / max(1, m.words)) - 15.59, 1)
    return m


def reading_cost(m: Measures) -> float:
    """One number to rank by. Not a score of quality: the tax a reader pays per hundred words,
    weighted toward the things that make him re-read — long sentences, walls, nesting."""
    if not m.words:
        return 0.0
    cost = 0.0
    cost += 40 * m.long_sentence_share
    cost += 2.0 * m.very_long_sentences / max(1, m.sentences) * 10
    cost += 0.08 * max(0, m.words_per_paragraph - 60)
    cost += 6 * m.walls + 0.01 * m.longest_wall
    cost += 8 * m.parens_per_sentence
    cost += 10 * m.passive_share
    cost += 0.3 * max(0, m.nominal_per_100 - 6)
    cost += 0.5 * max(0, m.grade - 12)
    cost += 0.4 * max(0, m.code_per_100 - DENSE_CODE)
    cost += 0.5 * m.hedges
    return round(cost, 1)


# ---------------------------------------------------------------- sections

@dataclass
class Section:
    file: str
    heading: str
    level: int
    line: int
    measures: Measures = field(default_factory=Measures)
    worst_sentences: list[tuple[int, str]] = field(default_factory=list)
    wall_lines: list[tuple[int, int]] = field(default_factory=list)


def split_sections(blocks: list[Block], file: str) -> list[Section]:
    """A section is an h2 or h3 and everything to the next heading of the same or higher level;
    text before the first heading is the preamble."""
    sections: list[Section] = []
    cur = Section(file, '(preamble)', 0, 1)
    body: list[Block] = []

    def close():
        if not body and cur.heading == '(preamble)':
            return
        cur.measures = measure_prose(prose_units(body))
        # Walls: consecutive body words with no entry point (heading, list, table, fence, quote).
        run = 0
        run_start = None
        for b in body:
            if b.kind == 'p':
                w = words(strip_inline(b.text))
                if run == 0:
                    run_start = b.line
                run += w
                if run >= WALL_WORDS and (not cur.wall_lines or cur.wall_lines[-1][0] != run_start):
                    cur.wall_lines.append((run_start, run))
                elif cur.wall_lines and cur.wall_lines[-1][0] == run_start:
                    cur.wall_lines[-1] = (run_start, run)
            else:
                run = 0
                run_start = None
                cur.measures.entry_points += 1
        cur.measures.walls = len(cur.wall_lines)
        cur.measures.longest_wall = max([w for _, w in cur.wall_lines] or [0])
        # The worst sentences, by length, with their line.
        worst = []
        for b in body:
            if b.kind not in ('p', 'list'):
                continue
            # Item by item, with each item's own line: twelve semicolon-ended bullets are
            # twelve items, not one 131-word sentence.
            for unit in prose_units([b]):
                line = b.line + (b.text[:b.text.find(unit[:20])].count('\n') if b.kind == 'list' and unit[:20] in b.text else 0)
                for s in sentences(strip_inline(unit)):
                    n = words(s)
                    if n > LONG_SENTENCE:
                        worst.append((n, line, s))
        worst.sort(reverse=True)
        # Every sentence over the very-long line is named, whatever the section's average: a
        # 137-word sentence in a section that otherwise reads well is still in the queue. Below
        # that line, the three longest.
        keep = [w for w in worst if w[0] > VERY_LONG_SENTENCE] or worst[:3]
        if len(keep) < 3:
            keep = worst[:3]
        cur.worst_sentences = [(ln, f'{n}w: {s[:110]}…' if len(s) > 110 else f'{n}w: {s}') for n, ln, s in keep]
        cur.measures.cost = reading_cost(cur.measures)
        sections.append(cur)

    for b in blocks:
        if b.kind == 'heading' and b.level <= 3:
            close()
            cur = Section(file, b.text, b.level, b.line)
            body = []
        else:
            body.append(b)
    close()
    return sections


def document_measures(blocks: list[Block]) -> Measures:
    m = measure_prose(prose_units(blocks))
    m.cost = reading_cost(m)
    return m


# ---------------------------------------------------------------- audit / check output

def fmt_section(s: Section, with_file: bool) -> str:
    m = s.measures
    name = f'{s.file}: ' if with_file else ''
    head = f'{name}{"#" * max(1, s.level)} {s.heading}'
    line = (f'{head}  [cost {m.cost:>5}]  {m.words}w  {m.words_per_sentence} w/sent  '
            f'long {int(m.long_sentence_share * 100)}%  {m.words_per_paragraph} w/para  '
            f'walls {m.walls}' + (f' ({m.longest_wall}w)' if m.walls else '') +
            f'  code {m.code_per_100}/100  grade {m.grade}')
    return line


def cmd_check(args) -> int:
    path = Path(args.file)
    md = path.read_text(encoding='utf-8')
    blocks = parse(md)
    doc = document_measures(blocks)
    print(f'{path.name}: {doc.words} words, {doc.sentences} sentences, {doc.words_per_sentence} words/sentence, '
          f'{int(doc.long_sentence_share * 100)}% over {LONG_SENTENCE}, grade {doc.grade}, cost {doc.cost}')
    sections = split_sections(blocks, path.name)
    if args.section:
        sections = [s for s in sections if args.section.lower() in s.heading.lower()]
    for s in sections:
        print(fmt_section(s, with_file=False))
        for start, w in s.wall_lines:
            print(f'   [wall] {w} words with no entry point from line {start}')
        for ln, text in s.worst_sentences:
            print(f'   [long] line {ln}: {text}')
        if s.measures.hedges:
            print(f'   [filler] {s.measures.hedges} hedge or filler phrase(s) ("in order to", "note that", "the fact that"…)')
    return 0


def cmd_audit(args) -> int:
    root = Path(args.path)
    files = [root] if root.is_file() else sorted(root.rglob('*.md'))
    excluded = []
    keep = []
    for f in files:
        rel = str(f.relative_to(root) if root.is_dir() else f)
        if any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(f.name, g) for g in (args.exclude or [])) or 'node_modules' in f.parts:
            excluded.append(f)
        else:
            keep.append(f)
    rows: list[Section] = []
    docs = []
    for f in keep:
        try:
            md = f.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        blocks = parse(md)
        dm = document_measures(blocks)
        docs.append((f, dm))
        rows.extend(split_sections(blocks, str(f.relative_to(root) if root.is_dir() else f.name)))
    rows = [r for r in rows if r.measures.words >= 60]
    rows.sort(key=lambda r: r.measures.cost, reverse=True)
    total_words = sum(d.words for _, d in docs)
    walls = sum(r.measures.walls for r in rows)
    print(f'{len(docs)} document(s), {total_words} words, {len(rows)} section(s) of 60+ words, {walls} wall(s); '
          f'{len(excluded)} file(s) excluded')
    if docs:
        worst_docs = sorted(docs, key=lambda d: d[1].cost, reverse=True)
        print('documents by cost:')
        for f, d in worst_docs[: args.top]:
            print(f'  {d.cost:>6}  {d.words:>6}w  {d.words_per_sentence:>5} w/sent  long {int(d.long_sentence_share * 100):>3}%  grade {d.grade:>5}  {f.name}')
    print('sections by cost:')
    for r in rows[: args.top]:
        print('  ' + fmt_section(r, with_file=True))
    if args.json:
        out = {
            'documents': [{'file': str(f), **asdict(d)} for f, d in docs],
            'sections': [{'file': r.file, 'heading': r.heading, 'line': r.line, **asdict(r.measures),
                          'walls_at': r.wall_lines, 'worst': r.worst_sentences} for r in rows],
        }
        Path(args.json).write_text(json.dumps(out, indent=2), encoding='utf-8')
        print(f'wrote {args.json}')
    return 0


# ---------------------------------------------------------------- the fidelity gate

IDENT_RE = re.compile(r'''
    (?<![\w`])(
      [A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*){1,}      # dotted: Maestro.Orchestra.Execution, foo.bar
    | [A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+           # CamelCase
    | [a-z]+(?:_[a-z0-9]+)+                        # snake_case
    | [a-z][a-z0-9]*(?:-[a-z0-9]+){1,}(?:\.\w+)?   # kebab-case-words, with an extension
    | (?:[A-Za-z]:)?[\w.-]*[/\\][\w./\\-]+         # paths
    | --?[a-z][\w-]*                               # CLI flags
    | [A-Z]{2,}(?:-\d+)?                           # acronyms and T-153 style ids
    | [A-Z]-\d+                                    # P-01, Q-3
    | §\s?\d+(?:\.\d+)*                            # section references
    | Q\d+                                         # Q12
    )(?![\w`])
''', re.X)
NUMBER_RE = re.compile(r'(?<![\w.\-])(\d+(?:[.,]\d+)*)(?:\s?(%|ms|s|m|h|d|min|px|pt|in|em|MB|GB|KB|u|x))?(?![\w.])')
REF_RE = re.compile(r'\[([^\]]*)\]\(([^)\s]+)\)')

# Words that look like identifiers but are ordinary English at a sentence start.
COMMON_CAPS = {'OK', 'ID', 'IDS', 'AI', 'API', 'UI', 'UX', 'CI', 'CLI', 'PR', 'PRS', 'AC', 'ACS', 'TODO', 'NOTE', 'IO'}


def plain(s: str) -> str:
    """Inline markup off, words kept: a heading or cell compared by its own words, numeral and all."""
    return re.sub(r"[*_`~]", "", LINK_RE.sub(r"\1", s))


def norm(s: str) -> str:
    return re.sub(r'\s+', ' ', s.replace('’', "'").replace('“', '"').replace('”', '"')).strip().lower()


def facts(md: str) -> dict[str, list[tuple[str, int]]]:
    """Everything in a document that carries a fact by its exact form, each with its line."""
    blocks = parse(md)
    out = {'code': [], 'ident': [], 'number': [], 'ref': [], 'heading': [], 'cell': [], 'fence': []}
    for b in blocks:
        if b.kind == 'fence':
            out['fence'].append((b.lang + '\n' + b.text, b.line))
            continue
        if b.kind == 'heading':
            out['heading'].append((norm(plain(b.text)), b.line))
        if b.kind == 'table':
            for i, row in enumerate(b.text.split('\n')):
                if re.match(r'^\s*\|?[\s:|-]+\|[\s:|-]*$', row):
                    continue
                for cell in row.strip().strip('|').split('|'):
                    c = norm(plain(cell))
                    if c:
                        out['cell'].append((c, b.line + i))
        text = b.text
        for m in CODE_SPAN_RE.finditer(text):
            out['code'].append((m.group(1).strip(), b.line))
        for m in REF_RE.finditer(text):
            out['ref'].append((m.group(2), b.line))
        prose = CODE_SPAN_RE.sub(' ', text)
        prose = REF_RE.sub(r'\1', prose)
        for m in IDENT_RE.finditer(prose):
            tok = m.group(1)
            if tok.upper() in COMMON_CAPS or len(tok) < 3:
                continue
            out['ident'].append((tok, b.line))
        for m in NUMBER_RE.finditer(prose):
            out['number'].append((m.group(0).strip(), b.line))
    return out


def present(kind: str, value: str, after_text: str, after_norm: str, after_facts) -> bool:
    if kind == 'fence':
        return value in {v for v, _ in after_facts['fence']}
    if kind == 'code':
        v = value.strip()
        return v in {c for c, _ in after_facts['code']} or v in after_text
    if kind in ('heading', 'cell'):
        return value in after_norm
    if kind == 'ref':
        return value in after_text
    if kind == 'ident':
        # exact, or the identifier written with spaces ("Internal API" for InternalAPI), or as
        # part of a longer dotted path.
        if value in after_text:
            return True
        spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', value).replace('_', ' ').replace('-', ' ')
        if spaced.lower() in after_norm:
            return True
        return False
    if kind == 'number':
        # "30 s" and "30s" are the same fact; the space between number and unit is free.
        pat = re.escape(value).replace(r'\ ', r'\s?')
        return re.search(r'(?<![\w.])' + pat + r'(?![\w])', after_text) is not None
    return False


# The defect every cold reader found, round after round: a sentence that tied a consequence to
# its cause ("…, so any repo's tests fit the manifest and the script is a legacy alias") is split
# in two, and the second half stands as a bare assertion. The gate cannot see meaning, but it
# can see this shape: a clause that followed a causal connective in the before and is present
# in the after without any causal connective within reach of it.
CAUSAL_RE = re.compile(r'(?<!\bif )(?<!\bor )(?<!\beven )\b(?:so(?! on\b)(?! far\b)(?! that\b)|because|since|therefore|hence|thus|which means|which is why)\b[,:]?\s+', re.I)
CAUSAL_REACH = 160   # characters back from the clause in which a connective must still appear


CLAUSE_SPLIT_RE = re.compile(r',?\s+and\s+|;\s+|,\s+(?=[a-z])')


def causal_clauses(text: str) -> list[tuple[str, str]]:
    """(connective, the first five words of each clause that hung on it). A "so" can carry three
    coordinated consequences; the one that gets cut loose is never the first."""
    out = []
    for m in CAUSAL_RE.finditer(text):
        tail = text[m.end():]
        stop = CAUSAL_RE.search(tail)
        if stop:
            tail = tail[:stop.start()]
        # Three coordinated consequences is the shape; a semicolon list of twelve is a list.
        for clause in CLAUSE_SPLIT_RE.split(tail)[:3]:
            head = WORD_RE.findall(clause)[:5]
            if len(head) >= 4 and sum(1 for w in head if w.isalpha()) >= 3:
                out.append((m.group(0).strip(' ,:'), ' '.join(head)))
    return out


def lost_causal_links(before: str, after: str) -> list[tuple[str, str, int]]:
    after_norm = norm(strip_inline(after))
    lost = []
    for b in parse(before):
        if b.kind not in ('p', 'list'):
            continue
        # A list is scanned item by item, or a "so" in one item would claim the items after it.
        for unit in prose_units([b]):
            for s in sentences(strip_inline(unit)):
                for connective, clause in causal_clauses(s):
                    key = norm(clause)
                    # Match on the clause's own words, punctuation aside.
                    pat = re.compile(r'\W+'.join(re.escape(w) for w in key.split()))
                    hits = list(pat.finditer(after_norm))
                    if not hits:
                        continue          # reworded past recognition: the fact gate rules on that
                    # The cause must sit in the same sentence as the consequence, before or after
                    # it ("…, so it gets a rule"): the sentence around the hit, within reach. A
                    # clause the document states twice passes if either copy keeps its cause.
                    attached = False
                    for hit in hits:
                        lo = max(0, hit.start() - CAUSAL_REACH)
                        hi = min(len(after_norm), hit.end() + CAUSAL_REACH)
                        window = after_norm[lo:hi]
                        rel = hit.start() - lo
                        cut = max(window.rfind('. ', 0, rel), window.rfind('? ', 0, rel), window.rfind('! ', 0, rel))
                        if cut >= 0:
                            window = window[cut + 2:]
                        end = re.search(r'[.?!] ', window[rel - (cut + 2 if cut >= 0 else 0):])
                        if end:
                            window = window[:rel - (cut + 2 if cut >= 0 else 0) + end.start()]
                        if CAUSAL_RE.search(window):
                            attached = True
                            break
                    if not attached:
                        lost.append((connective, clause, b.line))
    return lost


def cmd_diff(args) -> int:
    before = Path(args.before).read_text(encoding='utf-8')
    after = Path(args.after).read_text(encoding='utf-8')
    bf = facts(before)
    af = facts(after)
    # Headings and cells are compared by their own words, code spans included: plain(), not
    # strip_inline(), which would turn every `name` into CODE and match nothing.
    after_norm = norm(plain(after))
    lost: list[tuple[str, str, int]] = []
    warned: list[tuple[str, str, int]] = []
    changed: list[tuple[str, str, int]] = []
    seen = set()
    for kind, items in bf.items():
        for value, line in items:
            key = (kind, value)
            if key in seen:
                continue
            seen.add(key)
            if present(kind, value, after, after_norm, af):
                continue
            if kind == 'fence':
                lost.append((kind, (value.split('\n', 1)[0] or 'code') + ' fence', line))
            elif kind == 'number' and len(re.sub(r'\D', '', value)) >= EXAMPLE_NUMBER_DIGITS:
                warned.append((kind, value, line))
            elif kind in ('heading', 'cell'):
                changed.append((kind, value, line))
            else:
                lost.append((kind, value, line))
    wb = words(strip_inline(before))
    wa = words(strip_inline(after))
    mb = document_measures(parse(before))
    ma = document_measures(parse(after))
    print(f'words {wb} -> {wa} ({(wa - wb) * 100 // max(1, wb):+d}%); words/sentence {mb.words_per_sentence} -> {ma.words_per_sentence}; '
          f'long sentences {int(mb.long_sentence_share * 100)}% -> {int(ma.long_sentence_share * 100)}%; '
          f'walls {mb.walls} -> {ma.walls}; grade {mb.grade} -> {ma.grade}; cost {mb.cost} -> {ma.cost}')
    total = sum(len(v) for v in bf.values())
    print(f'facts checked: {total} ({", ".join(f"{k} {len(v)}" for k, v in bf.items())})')
    for kind, value, line in warned:
        print(f'   [dropped example] {kind} {value!r} (line {line}) — a number of {EXAMPLE_NUMBER_DIGITS}+ digits is treated as an example value')
    for kind, value, line in changed:
        print(f'   [changed] {kind} {value!r} (line {line}) is gone: a heading or cell may be reworded, but say so')
    for kind, value, line in lost:
        print(f'   [DESTROYED] {kind} {value!r} (line {line}) is nowhere in the after')
    causal = lost_causal_links(before, after)
    for connective, clause, line in causal:
        print(f'   [causal] line {line}: "{connective} {clause}…" — the consequence is in the after with no cause attached; re-join it or say why')
    if causal:
        print(f'CAUSAL: {len(causal)} consequence(s) cut from their cause — fix before the cold reader does (exit 1)')
    if lost:
        if args.declare:
            print(f'declared: {args.declare} — a declaration does not excuse a lost fact; put it back or move it to prose')
        print(f'DESTROYED: {len(lost)} fact(s) lost — the edit is refused (exit 2)')
        return 2
    if changed:
        print(f'CHANGED: {len(changed)} heading(s) or cell(s) reworded or removed (exit 1)' + (f' — declared: {args.declare}' if args.declare else ''))
        return 0 if args.declare and not causal else 1
    if causal:
        return 1
    if ma.cost > mb.cost:
        print(f'WARNING: reading cost rose ({mb.cost} -> {ma.cost}); the edit made it harder to read')
    print('KEPT: every fact in the before is in the after (exit 0)')
    return 0


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('audit')
    a.add_argument('path')
    a.add_argument('--json')
    a.add_argument('--exclude', nargs='*')
    a.add_argument('--top', type=int, default=25)
    a.set_defaults(fn=cmd_audit)
    c = sub.add_parser('check')
    c.add_argument('file')
    c.add_argument('--section')
    c.set_defaults(fn=cmd_check)
    d = sub.add_parser('diff')
    d.add_argument('before')
    d.add_argument('after')
    d.add_argument('--declare')
    d.set_defaults(fn=cmd_diff)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
