#!/usr/bin/env python3
"""Measure diagrams: what type they are, how legible they render, and what they assert.

Four jobs, all of which the /diagram skill depends on:

  audit    walk a tree, render every diagram, and report what is wrong with each
  graph    extract a diagram's semantic content — nodes, edges, members, direction — so a
           rewrite can be diffed against the original and prove nothing was lost
  diff     compare the graphs of a before file and one or more after files, and say
           IDENTICAL, CHANGED (with the lists) or UNVERIFIABLE when a side cannot be parsed
  check    gate one diagram: label length, legibility at target size, type fit

The measurement that matters most is label point size AT THE TARGET WIDTH. A diagram that
looks fine on a monitor prints at 3pt, and the cause is almost always label length: long
labels make wide nodes, wide nodes make a wide diagram, and a wide diagram is scaled down
to fit. Which text drives the width differs by type — a flowchart's node labels, a sequence
diagram's message text, a class diagram's members, a gantt's task names — so the measurement
is taken from the rendered SVG, where every piece of text is present with its real size,
and the widest run is reported as the width driver.

Honesty rules the tool keeps:
  - a kind the parser cannot read is reported as unparsed; `graph` says so and `diff`
    refuses a verdict rather than certifying 0 = 0
  - every digit-only hex is named, not just the first
  - directories that hold test fixtures are skipped by default, and the count is printed,
    so a corpus statistic is not poisoned by files written to fail

Usage:
  python audit.py audit <path> [--target md|ado|magazine] [--json out.json] [--exclude X]
  python audit.py graph <file.mmd|file.md|file.gv>
  python audit.py diff <before> <after> [<after2> ...]
  python audit.py check <file> [--target ...] [--json out.json]
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
import importlib.util


def _sibling(path: Path):
    """Load a helper module by path, so this file finds its siblings however it was started
    (as a script, or loaded by path by the publish board)."""
    name = f"_diagram_{path.stem}"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


HERE = Path(__file__).resolve().parent
fences = _sibling(HERE / "fences.py")        # what a diagram fence is: shared with edit, publish, magazine
presence = _sibling(HERE / "presence.py")    # when a shortened identifier is still present: shared with edit
# The magazine target is measured the way the magazine prints: the builder, installed beside this
# skill, supplies its mermaid config and places every figure (magazine_placement). This file keeps
# no copy of the magazine's page; one once disagreed with the builder by a factor of three.
MAGAZINE_DIR = HERE.parents[1] / "magazine"
MAGAZINE_BUILD = MAGAZINE_DIR / "scripts" / "build-magazine.mjs"


# Target widths in inches. These are not measurements of any surface: 6.5in is the floor Edward
# chose (2026-09-19) as the strictest realistic width — a wiki column, a printed page inside its
# margins, a narrow browser window. A diagram legible at 6.5in is legible everywhere it will be
# read, which is the skill's own rule of authoring to the strictest target. The question of
# widening it is closed. The magazine has no width here: the builder places each figure on the
# page, fit to its height as well as its width, and says at what scale.
TARGETS = {
    "md": 6.5,         # the chosen floor; a README is not assumed wider than a wiki page
    "ado": 6.5,        # the chosen floor, not an observed ADO column width
    "magazine": None,  # placed by the magazine builder, never a fixed width
}


def _surface(target: str, rep: "DiagramReport | None" = None) -> str:
    """Where a figure prints, as a finding says it: a width, or the magazine's own placement."""
    if target != "magazine":
        return f"at {TARGETS[target]}in wide"
    return f"placed as the magazine's '{rep.placement}'" if rep and rep.placement else "in the magazine"
LABEL_FLOOR_PT = 7.0       # below this, a printed label is not read, it is guessed at
LABEL_TARGET_PT = 8.0      # what to aim for, so the floor is not the design
MAX_LABEL_WORDS = 3        # Edward's rule: three words, one preferred
NOTE_MAX_WORDS = 20        # a note or a title is prose by design; past this it is a paragraph
NODE_BUDGET = 12           # past this an overview should split (a comfortable range is 5-10)
DEFAULT_FONT_PX = 16.0     # mermaid's default; graphviz's is 14
CHAR_WIDTH_EM = 0.55       # average glyph width in a UI sans, for widths the SVG does not give

# Directories that hold diagrams written to fail a validator. Skipped unless asked for.
FIXTURE_DIRS = {"fixture", "fixtures", "__fixtures__", "testdata", "__snapshots__", "node_modules", ".git"}

HEX_COLOR = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
INIT_DIRECTIVE = re.compile(r"%%\{\s*init\s*:", re.I)
# An id may carry dots and hyphens inside (a.b, first-step) but never swallow an arrow: `A-->B`
# is A, an arrow, B.
ID = r"[A-Za-z_]\w*(?:[.-]\w+)*"


@dataclass
class Finding:
    severity: str          # blocker | warning | nit
    code: str
    detail: str


@dataclass
class TextRun:
    role: str              # node | edge | member | note | title | axis | other
    text: str
    px: float
    width_px: float        # measured when the renderer gives it, estimated otherwise
    measured: bool


@dataclass
class Graph:
    kind: str
    parsed: bool
    nodes: dict[str, str] = field(default_factory=dict)          # id -> label
    edges: list[tuple[str, str, str]] = field(default_factory=list)
    members: dict[str, list[str]] = field(default_factory=dict)  # id -> attributes/fields
    note: str = ""
    title: str = ""
    notes: list[str] = field(default_factory=list)   # visible notes, part of the diagram's scope


@dataclass
class DiagramReport:
    path: str
    index: int = 0
    kind: str = "unknown"
    direction: str = ""
    parsed: bool = False
    nodes: int = 0
    edges: int = 0
    node_labels: list[str] = field(default_factory=list)
    max_label_words: int = 0
    median_label_words: float = 0.0
    long_labels: list[str] = field(default_factory=list)
    max_edge_words: int = 0
    long_edge_labels: list[str] = field(default_factory=list)
    long_notes: list[str] = field(default_factory=list)
    back_edges: int = 0
    multi_parent_nodes: int = 0
    rendered: bool = False
    native_w: float = 0.0
    native_h: float = 0.0
    height_at_target_px: float = 0.0     # how tall it prints once scaled to the target width
    measure_error: str = ""              # set when the render could not be measured: the gate refuses
    structural_pt: float = 0.0           # the best any label can do given the diagram's fixed geometry
    structural_reason: str = ""          # what fixes that geometry ("6 participants")
    placement: str = ""                  # magazine target only: the builder's placement class
    in_document: bool = False            # a figure in a .md, which must carry a title and caption
    title: str | None = None             # the bold line just above the fence
    caption: str | None = None           # the italic line just below it
    layout_defects: list[str] = field(default_factory=list)  # overflow and strike-through, measured
    label_pt_at_target: float = 0.0      # smallest node/edge/member text at the target width
    smallest_text_pt: float = 0.0        # smallest text of any role, for the record
    width_driver: dict = field(default_factory=dict)   # the run that sets the diagram's width
    text_runs: int = 0
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity: str, code: str, detail: str) -> None:
        self.findings.append(Finding(severity, code, detail))

    @property
    def worst(self) -> str:
        for level in ("blocker", "warning", "nit"):
            if any(f.severity == level for f in self.findings):
                return level
        return "clean"


# ----------------------------------------------------------------- extraction

def figure_labels(path: Path) -> list[tuple[str | None, str | None]] | None:
    """(title, caption) for each diagram in a markdown document, in extract_diagrams' order;
    None for a raw .mmd/.dot, whose title and caption live in the document that embeds it."""
    if path.suffix.lower() in (".mmd", ".mermaid", ".dot", ".gv"):
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = fences.split_lines(text)
    return [fences.labels(lines, f) for f in fences.scan(text) if f.diagram]


def extract_diagrams(path: Path) -> list[tuple[int, str, bool]]:
    """Return (index, source, was_fenced) for every diagram in a file.

    A .mmd holds exactly one diagram and is raw source (the repo convention this tool assumes). A .md may hold
    several, in any diagram fence fences.json defines (``` ~~~ or Azure DevOps's :::, mermaid or
    Graphviz). A .dot/.gv is Graphviz.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in (".mmd", ".mermaid"):
        body = re.sub(r"^---\r?\n.*?\r?\n---\r?\n", "", text, count=1, flags=re.S)
        fenced = False
        body_lines = body.splitlines()
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        while body_lines and not body_lines[-1].strip():
            body_lines.pop()
        o = fences.opener(body_lines[0]) if body_lines else None
        if o and o[1].lower() in fences.DIAGRAM_LANGS:
            fenced = True
            body_lines.pop(0)
            if body_lines and fences.is_closer(body_lines[-1], o[0]):
                body_lines.pop()
        return [(0, "\n".join(body_lines), fenced)]
    if path.suffix.lower() in (".dot", ".gv"):
        return [(0, text, False)]

    lines = fences.split_lines(text)
    found = [f for f in fences.scan(text) if f.diagram]
    return [(n, "\n".join(lines[f.start + 1:f.end]), False) for n, f in enumerate(found)]


def strip_comments(src: str) -> str:
    """Drop mermaid %% lines, Graphviz // and /* */ comments, and a leading frontmatter block."""
    s = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    s = re.sub(r"^---\r?\n.*?\r?\n---\r?\n", "", s, count=1, flags=re.S)
    out = []
    for ln in s.splitlines():
        t = ln.strip()
        if t.startswith("%%") and not t.startswith("%%{"):
            continue
        if t.startswith("//"):
            continue
        # a trailing // comment, outside quotes
        if "//" in ln and ln.count('"') % 2 == 0:
            ln = re.sub(r'(?<!["\w:])//(?!.*").*$', "", ln)
        out.append(ln)
    return "\n".join(out)


def detect_kind(src: str) -> tuple[str, str]:
    head = "\n".join(
        ln for ln in strip_comments(src).splitlines() if ln.strip() and not ln.strip().startswith("%%")
    )[:600]
    if re.search(r"^\s*(strict\s+)?(digraph|graph)\s+[\w\"]*\s*\{", head, re.M):
        return "graphviz", ""
    m = re.search(r"^\s*(flowchart|graph)\s+(TB|TD|BT|LR|RL)\b", head, re.M)
    if m:
        return "flowchart", m.group(2)
    for key, kind in (
        ("C4Context", "c4"), ("C4Container", "c4"), ("C4Component", "c4"), ("C4Dynamic", "c4"),
        ("C4Deployment", "c4"),
        ("requirementDiagram", "requirement"), ("quadrantChart", "quadrant"), ("sankey", "sankey"),
        ("block-beta", "block"), ("sequenceDiagram", "sequence"), ("stateDiagram", "state"),
        ("erDiagram", "er"), ("classDiagram", "class"), ("gantt", "gantt"), ("journey", "journey"),
        ("mindmap", "mindmap"), ("timeline", "timeline"), ("pie", "pie"), ("xychart", "xychart"),
        ("gitGraph", "gitgraph"),
    ):
        if re.search(rf"^\s*{key}", head, re.M):
            return kind, ""
    return "unknown", ""


def svg_lines(inner: str) -> list[str]:
    """The visible lines of an SVG <text>: one per <tspan> (a wrapped label), else the text."""
    parts = re.split(r"<tspan\b[^>]*>", inner)
    lines = [strip_markup(p) for p in parts]
    return [l for l in lines if l] or ([strip_markup(inner)] if strip_markup(inner) else [])


def strip_markup(label: str) -> str:
    # a tag starts with a lower-case letter (br, b, tspan, div…); `Create<IApiClient>()` is a
    # generic type argument, not markup, and stays
    s = re.sub(r"<br\s*/?>|<tspan\b[^>]*>", " ", label, flags=re.I)
    s = re.sub(r"</?[a-z][a-z0-9]*(?:\s[^>]*)?/?>", "", s)
    s = re.sub(r"&[a-z]+;|&#\d+;", " ", s)
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'`":
        s = s[1:-1]
    return re.sub(r"\s+", " ", s).strip()


def words(label: str) -> int:
    return len([w for w in strip_markup(label).split() if w])


# ----------------------------------------------------------------- quote masking

def mask_quotes(text: str) -> tuple[str, list[str]]:
    """Replace every double-quoted string with a placeholder so structural regexes never
    match inside a label. The placeholders restore to the original text, quotes included."""
    store: list[str] = []

    def keep(m: re.Match) -> str:
        store.append(m.group(0))
        return f"\x00{len(store) - 1}\x00"

    return re.sub(r'"[^"\n]*"', keep, text), store


def unmask(text: str, store: list[str]) -> str:
    return re.sub(r"\x00(\d+)\x00", lambda m: store[int(m.group(1))], text)


# ----------------------------------------------------------------- parsers

NODE_DECL = re.compile(
    rf"""(?P<id>{ID})\s*
        (?:\(\[(?P<stadium>[^\]]*)\]\)
          |\[\[(?P<subroutine>[^\]]*)\]\]
          |\[\((?P<cylinder>[^)]*)\)\]
          |\(\((?P<circle>[^)]*)\)\)
          |\{{\{{(?P<hexagon>[^}}]*)\}}\}}
          |\[(?P<rect>[^\]]*)\]
          |\((?P<round>[^)]*)\)
          |\{{(?P<rhombus>[^}}]*)\}}
          |>(?P<flag>[^\]]*)\]
        )""",
    re.X,
)
# A flowchart line, once every `id[label]` is reduced to its id, is a sequence of id groups
# (`A`, `A & B`) separated by links; every link carries its label either as `|text|` after
# the arrow or as `-- text -->` inside it. `~~~` is an invisible layout link and asserts nothing.
FLOW_ARROW = (
    r"(?P<ta>--|-\.|==)\s*(?P<text>[^-=.|<>\s][^|<>]*?)\s*(?P<tb>-->|---|\.->|\.-|==>|===)"  # A -- text --> B
    r"|(?P<arrow>[xo<]?(?:-{2,}|={2,}|-\.+-)[>xo]?)(?:\s*\|(?P<label>[^|]*)\|)?"                # A -->|text| B
)
FLOW_TOKEN = re.compile(rf"(?P<ids>{ID}(?:\s*&\s*{ID})*)|{FLOW_ARROW}|(?P<invisible>~~~)")
FLOW_KEYWORD = re.compile(r"^(flowchart|graph|subgraph|end|direction|classDef|class|style|linkStyle|click)\b")
SEQ_MSG = re.compile(r"^\s*(?P<from>[\w\"' -]+?)\s*(?P<arrow>-?-(?:>>|>|x|\))|\.\.>>?)\s*(?P<to>[\w\"' -]+?)\s*:\s*(?P<label>.*)$")


def parse_flowchart(body: str) -> Graph:
    g = Graph("flowchart", True)
    masked, store = mask_quotes(body)
    for ln in masked.splitlines():
        s = ln.strip()
        # keywords are matched whole: a node named `endpoint` or `classifier` is a node
        if not s or FLOW_KEYWORD.match(s):
            continue
        s = re.sub(r":::\w[\w-]*", "", s)                      # A:::className
        s = re.sub(r"@\{[^}]*\}", "", s)                        # A@{shape: ...}
        for m in NODE_DECL.finditer(s):
            label = next((v for k, v in m.groupdict().items() if k != "id" and v is not None), "")
            g.nodes[m.group("id")] = strip_markup(unmask(label, store))
        reduced = NODE_DECL.sub(lambda m: m.group("id"), s)     # A[Alpha] --> B[Beta]  ==>  A --> B
        prev: list[str] = []
        pending: str | None = None
        for t in FLOW_TOKEN.finditer(reduced):
            if t.group("ids"):
                ids = re.findall(ID, t.group("ids"))
                for x in ids:
                    g.nodes.setdefault(x, x)
                if pending is not None and prev:
                    for a in prev:
                        for b in ids:
                            g.nodes.setdefault(a, a); g.nodes.setdefault(b, b)
                            g.edges.append((a, b, pending))
                prev, pending = ids, None
            elif t.group("invisible"):
                prev, pending = [], None
            else:
                raw = t.group("text") if t.group("text") is not None else (t.group("label") or "")
                pending = strip_markup(unmask(raw, store)).strip()
    seen = set()
    uniq = []
    for e in g.edges:
        if e not in seen:
            seen.add(e); uniq.append(e)
    g.edges = uniq
    return g


def parse_sequence(body: str) -> Graph:
    g = Graph("sequence", True)
    for ln in body.splitlines():
        m = re.match(r"\s*(?:participant|actor)\s+(\S+)(?:\s+as\s+(.*))?", ln)
        if m:
            g.nodes[m.group(1)] = strip_markup(m.group(2) or m.group(1))
            continue
        n = re.match(r"\s*Note\s+(?:over|right of|left of)\s+[^:]+:\s*(.*)$", ln, re.I)
        if n:
            g.notes.append(strip_markup(n.group(1)))
            continue
        m = SEQ_MSG.match(ln)
        if m and not re.match(r"\s*(Note|loop|alt|else|opt|par|and|rect|end|critical|break|box)\b", ln):
            a, b = strip_markup(m.group("from")), strip_markup(m.group("to"))
            g.nodes.setdefault(a, a); g.nodes.setdefault(b, b)
            g.edges.append((a, b, strip_markup(m.group("label"))))
    return g


def parse_pie(body: str) -> Graph:
    """A pie asserts its slices: each quoted label is an entity and its value a member, so a
    redraw that drops or renames a slice is CHANGED and one that only recolours is IDENTICAL."""
    g = Graph("pie", True)
    for ln in body.splitlines():
        t = re.match(r"\s*pie\b(?:\s+showData)?(?:\s+title\s+(.*))?$", ln)
        if t:
            g.title = strip_markup(t.group(1) or "")
            continue
        t = re.match(r"\s*title\s+(.*)$", ln)
        if t:
            g.title = strip_markup(t.group(1))
            continue
        m = re.match(r'\s*"([^"]+)"\s*:\s*([\d.]+)', ln)
        if m:
            label = strip_markup(m.group(1))
            g.nodes[label] = label
            g.members[label] = [m.group(2)]
    return g


def _masked_lines(body: str) -> tuple[list[str], list[str]]:
    """Shared first step of every bracketed-block parser (state, class, er): mask quoted
    strings so a brace or keyword inside a label never confuses the walk, then hand back each
    line already stripped. Blank lines are dropped here since all three parsers skip them the
    same way — one `continue` on an empty line, wherever it falls in their own checks."""
    masked, store = mask_quotes(body)
    return store, [ln.strip() for ln in masked.splitlines() if ln.strip()]


def parse_state(body: str) -> Graph:
    g = Graph("state", True)
    store, lines = _masked_lines(body)
    in_note = False
    for s in lines:
        if in_note:
            if re.match(r"end\s+note\b", s):
                in_note = False
            elif s:
                g.notes.append(strip_markup(unmask(s, store)))
            continue
        if re.match(r"note\s+(right of|left of)\b", s):
            inline_note = re.match(r"note\s+(?:right of|left of)\s+\S+\s*:\s*(.+)$", s)
            if inline_note:
                g.notes.append(strip_markup(unmask(inline_note.group(1), store)))
            else:
                in_note = True
            continue
        # keywords matched whole: `endpoint --> X` and `classifier : x` are states, not keywords
        if not s or re.match(r"^(stateDiagram(?:-v2)?|classDef|class|direction|end|hide|show)\b", s):
            continue
        m = re.match(rf"state\s+(\x00\d+\x00)\s+as\s+({ID})", s)
        if m:
            g.nodes[m.group(2)] = strip_markup(unmask(m.group(1), store))
            continue
        m = re.match(rf"state\s+({ID})\s*\{{?", s)
        if m:
            g.nodes.setdefault(m.group(1), m.group(1))
            continue
        m = re.match(rf"(\[\*\]|{ID})\s*-->\s*(\[\*\]|{ID})\s*(?::\s*(.*))?$", s)
        if m:
            a, b = m.group(1), m.group(2)
            for x in (a, b):
                if x != "[*]":
                    g.nodes.setdefault(x, x)
            g.edges.append((a, b, strip_markup(unmask(m.group(3) or "", store))))
            continue
        m = re.match(rf"({ID})\s*:\s*(.+)$", s)
        if m:
            g.nodes.setdefault(m.group(1), m.group(1))
            g.members.setdefault(m.group(1), []).append(strip_markup(unmask(m.group(2), store)))
    return g


def parse_gantt(body: str) -> Graph:
    g = Graph("gantt", True)
    section = ""
    for ln in body.splitlines():
        s = ln.strip()
        if not s or re.match(r"^(gantt|title|dateFormat|axisFormat|excludes|todayMarker|tickInterval|weekday|inclusiveEndDates)\b", s):
            continue
        m = re.match(r"section\s+(.*)$", s)
        if m:
            section = strip_markup(m.group(1))
            g.nodes[f"section:{section}"] = section
            continue
        m = re.match(r"(.+?)\s*:\s*(.*)$", s)
        if m:
            name = strip_markup(m.group(1))
            parts = [p.strip() for p in m.group(2).split(",")]
            tags = {p for p in parts if p in ("done", "active", "crit", "milestone")}
            rest = [p for p in parts if p not in tags]
            tid = rest[0] if rest and re.match(r"^[A-Za-z_]\w*$", rest[0]) and not re.match(r"^after\b", rest[0]) else name
            g.nodes[tid] = name
            g.members.setdefault(tid, []).extend(sorted(tags))
            if section:
                g.edges.append((f"section:{section}", tid, "contains"))
            for dep in re.findall(r"after\s+(\w+)", m.group(2)):
                g.edges.append((dep, tid, "after"))
    return g


CLASS_REL = re.compile(
    rf"({ID})\s*(?P<rel>(?:<\|--|\*--|o--|-->|<--|--\|>|--\*|--o|\.\.\|>|<\|\.\.|\.\.>|<\.\.|\.\.|--|<-->|<\|--\|>))\s*"
    rf"(?:\x00\d+\x00\s*)?({ID})\s*(?::\s*(.*))?$"
)


def parse_class(body: str) -> Graph:
    g = Graph("class", True)
    store, lines = _masked_lines(body)
    current = None
    for s in lines:
        n = re.match(r"note(?:\s+for\s+\S+)?\s+(\x00\d+\x00)", s)
        if n:
            g.notes.append(strip_markup(unmask(n.group(1), store)).replace("\\n", " "))
            continue
        # keywords matched whole: a class named `notes` or `linkage` is a class
        if not s or re.match(r"^(classDiagram(?:-v2)?|note|direction|classDef|style|cssClass|link|click|callback|namespace)\b", s):
            continue
        if s == "}":
            current = None
            continue
        m = re.match(rf"class\s+({ID})(?:~[^\s{{]*)?\s*(\x00\d+\x00)?\s*(\{{)?", s)
        if m and not re.search(r"<\||-->|\.\.|--", s):
            cid = m.group(1)
            g.nodes[cid] = strip_markup(unmask(m.group(2), store)) if m.group(2) else cid
            g.members.setdefault(cid, [])
            current = cid if m.group(3) else None
            continue
        m = re.match(rf"({ID})\s*:\s*(.+)$", s)
        if m and not CLASS_REL.match(s):
            g.nodes.setdefault(m.group(1), m.group(1))
            g.members.setdefault(m.group(1), []).append(strip_markup(unmask(m.group(2), store)))
            continue
        m = CLASS_REL.match(s)
        if m:
            a, b = m.group(1), m.group(3)
            g.nodes.setdefault(a, a); g.nodes.setdefault(b, b)
            label = strip_markup(unmask(m.group(4) or "", store))
            g.edges.append((a, b, f"{m.group('rel')} {label}".strip()))
            continue
        if current and s not in ("{",):
            g.members.setdefault(current, []).append(strip_markup(unmask(s.strip("<<>>"), store)))
    return g


ER_REL = re.compile(
    rf"({ID})\s*(?P<card>(?:\|[|o{{}}]|}}[|o]|o[|{{]|\|\|)[-.]+(?:\|[|o{{}}]|[|o]{{|[|o]\||o\||\|\|))\s*({ID})\s*:\s*(.+)$"
)


def parse_er(body: str) -> Graph:
    g = Graph("er", True)
    store, lines = _masked_lines(body)
    current = None
    for s in lines:
        if s.startswith("erDiagram"):
            continue
        if s == "}":
            current = None
            continue
        m = ER_REL.match(s)
        if m:
            a, b = m.group(1), m.group(3)
            g.nodes.setdefault(a, a); g.nodes.setdefault(b, b)
            g.edges.append((a, b, f"{strip_markup(unmask(m.group(4), store))} [{m.group('card')}]"))
            continue
        m = re.match(rf"({ID})\s*(\x00\d+\x00)?\s*\{{", s)
        if m:
            current = m.group(1)
            g.nodes[current] = strip_markup(unmask(m.group(2), store)) if m.group(2) else current
            g.members.setdefault(current, [])
            continue
        if current:
            g.members[current].append(strip_markup(unmask(s, store)))
    return g


def split_args(arglist: str) -> list[str]:
    """Split a C4 macro's argument list on commas outside quotes, quotes stripped."""
    out, buf, q = [], "", False
    for ch in arglist:
        if ch == '"':
            q = not q
        elif ch == "," and not q:
            out.append(buf.strip().strip('"')); buf = ""
            continue
        buf += ch
    if buf.strip():
        out.append(buf.strip().strip('"'))
    return out


def parse_c4(body: str) -> Graph:
    g = Graph("c4", True)
    for ln in body.splitlines():
        s = ln.strip()
        m = re.match(r"(?P<macro>[A-Za-z_]+)\s*\((?P<args>.*)\)\s*\{?$", s)
        if not m:
            continue
        macro, args = m.group("macro"), split_args(m.group("args"))
        if macro.startswith(("Rel", "BiRel")):
            if len(args) >= 2:
                a, b = args[0], args[1]
                g.nodes.setdefault(a, a); g.nodes.setdefault(b, b)
                g.edges.append((a, b, " ".join(x for x in args[2:4] if x) + (" <->" if macro.startswith("BiRel") else "")))
            continue
        if macro in ("title", "UpdateLayoutConfig", "UpdateElementStyle", "UpdateRelStyle", "UpdateBoundaryStyle", "SHOW_LEGEND", "LAYOUT_WITH_LEGEND", "LAYOUT_TOP_DOWN", "LAYOUT_LEFT_RIGHT"):
            continue
        if re.match(r"(Person|System|Container|Component|Node|Deployment|Enterprise|Boundary)", macro) and len(args) >= 2:
            g.nodes[args[0]] = args[1]
            if macro.endswith("Boundary") or "Boundary" in macro:
                g.members.setdefault(args[0], []).append("boundary")
            elif len(args) >= 3 and args[2]:
                g.members.setdefault(args[0], []).append(args[2])
    return g


def parse_mindmap(body: str) -> Graph:
    g = Graph("mindmap", True)
    stack: list[tuple[int, str]] = []
    n = 0
    for ln in body.splitlines():
        if not ln.strip() or re.match(r"^(mindmap\s*$|%%|::icon|:::)", ln.strip()):
            continue
        indent = len(ln) - len(ln.lstrip())
        raw = ln.strip()
        m = re.match(r"(?:([A-Za-z_]\w*)(?=[\[({)]))?(?:\(\((.*)\)\)|\)\)(.*)\(\(|\)(.*)\(|\{\{(.*)\}\}|\[(.*)\]|\((.*)\)|(.*))$", raw)
        label = next((x for x in m.groups()[1:] if x is not None), raw) if m else raw
        label = strip_markup(label)
        nid = m.group(1) if m and m.group(1) else f"n{n}"
        n += 1
        g.nodes[nid] = label
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if stack:
            g.edges.append((stack[-1][1], nid, ""))
        stack.append((indent, nid))
    return g


GV_ID = r'(?:"[^"]*"|[A-Za-z_][\w]*|\d+)'


def parse_graphviz(body: str) -> Graph:
    g = Graph("graphviz", True)
    body = strip_comments(body)
    unq = lambda x: x.strip().strip('"')
    for ln in body.splitlines():
        s = ln.strip().rstrip(";")
        if not s or re.match(r"^(node|edge|graph)\s*\[", s) or re.match(r"^(strict\s+)?(digraph|graph|subgraph)\b", s) or s in ("{", "}") or re.match(r"^\w+\s*=", s):
            continue
        if "->" in s or re.search(r"\s--\s", s):
            attrs = re.search(r"\[(.*)\]\s*$", s)
            label = ""
            if attrs:
                lm = re.search(r'label\s*=\s*(?:"([^"]*)"|(\w+))', attrs.group(1))
                label = strip_markup(lm.group(1) or lm.group(2)) if lm else ""
                s = s[: attrs.start()]
            ids = [unq(x) for x in re.findall(GV_ID, s) if x.strip()]
            for a, b in zip(ids, ids[1:]):
                g.nodes.setdefault(a, a); g.nodes.setdefault(b, b)
                g.edges.append((a, b, label))
            continue
        m = re.match(rf"({GV_ID})\s*(?:\[(.*)\])?$", s)
        if m:
            nid = unq(m.group(1))
            label = nid
            if m.group(2):
                lm = re.search(r'label\s*=\s*(?:"([^"]*)"|<(.*)>|(\S+))', m.group(2))
                if lm:
                    label = strip_markup(lm.group(1) or lm.group(2) or lm.group(3))
            g.nodes[nid] = label
    return g


def parse_graph(src: str, kind: str) -> Graph:
    """Extract what the diagram asserts — nodes, edges, members — for the kinds the tool
    models. For any other kind the result says so: parsed=False, and the diff abstains."""
    body = strip_comments(src)
    body = "\n".join(ln for ln in body.splitlines() if not ln.strip().startswith("%%"))
    parsers = {
        "flowchart": parse_flowchart, "graphviz": parse_graphviz, "sequence": parse_sequence,
        "state": parse_state, "gantt": parse_gantt, "class": parse_class, "er": parse_er,
        "c4": parse_c4, "mindmap": parse_mindmap, "pie": parse_pie,
    }
    if kind in parsers:
        try:
            return parsers[kind](body)
        except Exception as exc:  # a parser fault is reported, never a silent empty graph
            return Graph(kind, False, note=f"parser error: {type(exc).__name__}: {exc}")
    return Graph(kind, False, note=f"no parser for {kind}: entities cannot be extracted from the source; verify a redraw by eye")


# ----------------------------------------------------------------- rendering

def _tool(name: str) -> str | None:
    return shutil.which(name) or shutil.which(name + ".cmd")


_magazine_config: tuple[Path, dict] | None = None


def magazine_mermaid_config(workdir: Path) -> tuple[Path | None, dict, str]:
    """(config file, config, complaint): the mermaid config the magazine renders with — its
    theme's spacing and fonts, its palette resolved — written by the builder itself, so a label
    measured here for the magazine is the label the magazine prints."""
    global _magazine_config
    if _magazine_config and _magazine_config[0].exists():
        return _magazine_config[0], _magazine_config[1], ""
    node = _tool("node")
    if not node or not MAGAZINE_BUILD.exists():
        return None, {}, f"the magazine target needs node and {MAGAZINE_BUILD}"
    out = workdir / "magazine-mermaid-config.json"
    try:
        r = subprocess.run([node, str(MAGAZINE_BUILD), "--mermaid-config", str(out)],
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not out.exists():
            return None, {}, f"the magazine builder could not write its mermaid config: {(r.stderr or r.stdout).strip()[:200]}"
        cfg = json.loads(out.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, {}, f"the magazine builder could not write its mermaid config: {str(exc)[:200]}"
    _magazine_config = (out, cfg)
    return out, cfg, ""


_magazine_placements: dict[tuple[float, float, str | None], dict] = {}


def magazine_placement(native_w: float, native_h: float, kind: str | None) -> tuple[dict | None, str]:
    """(placement, complaint): where the magazine builder itself places a figure of this native
    size, and at what scale — asked of the builder, never re-derived here, so a tall figure shrunk
    to the page height measures at the size it prints, not at its width-only size."""
    key = (round(native_w, 2), round(native_h, 2), kind)
    if key in _magazine_placements:
        return _magazine_placements[key], ""
    node = _tool("node")
    if not node or not MAGAZINE_BUILD.exists():
        return None, f"the magazine target needs node and {MAGAZINE_BUILD}"
    cmd = [node, str(MAGAZINE_BUILD), "--place", f"{native_w:.2f}x{native_h:.2f}"]
    if kind:
        cmd += ["--kind", kind]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return None, f"the magazine builder could not place the figure: {(r.stderr or r.stdout).strip()[:200]}"
        placement = json.loads(r.stdout)
    except Exception as exc:
        return None, f"the magazine builder could not place the figure: {str(exc)[:200]}"
    _magazine_placements[key] = placement
    return placement, ""


def render_svg(src: str, kind: str, workdir: Path, stem: str,
               config: Path | None = None) -> tuple[Path | None, str]:
    """Render to SVG; return (path or None, the renderer's complaint when it failed). A mermaid
    `config` file is passed to mmdc as-is."""
    if kind == "graphviz":
        dot = _tool("dot") or r"C:\Program Files\Graphviz\bin\dot.exe"
        if not Path(dot).exists() and not shutil.which("dot"):
            return None, "dot is not installed"
        out = workdir / f"{stem}.svg"
        try:
            r = subprocess.run([dot, "-Tsvg", "-o", str(out)], input=src, text=True,
                               capture_output=True, timeout=120)
            return (out, "") if out.exists() and r.returncode == 0 else (None, (r.stderr or "").strip()[:200])
        except Exception as exc:
            return None, str(exc)[:200]

    mmdc = _tool("mmdc")
    if not mmdc:
        return None, "mmdc is not installed"
    src_file = workdir / f"{stem}.mmd"
    out = workdir / f"{stem}.svg"
    src_file.write_text(src, encoding="utf-8")
    try:
        config_args = ["-c", str(config)] if config else []
        r = subprocess.run([mmdc, "-i", str(src_file), "-o", str(out), "-b", "transparent", *config_args],
                           capture_output=True, text=True, timeout=180, shell=(os.name == "nt"))
        if out.exists() and r.returncode == 0:
            return out, ""
        return None, (r.stderr or r.stdout or "").strip().splitlines()[-1:][0][:200] if (r.stderr or r.stdout) else "renderer failed"
    except Exception as exc:
        return None, str(exc)[:200]


# ----------------------------------------------------------------- the SVG text model

ROLE_BY_CLASS = [
    (re.compile(r"\bedgeLabel\b|\bmessageText\b|\bedgeTerminals\b|\brelationshipLabel\b"), "edge"),
    (re.compile(r"\bnodeLabel\b|\bactor\b|\btaskText\b|\bstateLabel\b|\bclassTitle\b|\btext-inner-tspan\b|\bentityLabel\b|\bsectionTitle\b"), "node"),
    (re.compile(r"\bnoteText\b|\bnoteLabel\b|\bnote\b|\bloopText\b|\blabelText\b"), "note"),
    (re.compile(r"TitleText\b|\btitle\b"), "title"),
    (re.compile(r"\btick\b|\bgrid\b|\baxis\b"), "axis"),
    (re.compile(r"\bslice\b"), "value"),   # a pie's percentage: computed by the renderer, not written by the author
]


def _role(cls: str, context: str) -> str:
    for rx, role in ROLE_BY_CLASS:
        if rx.search(cls):
            return role
    if context:
        return context
    return "other"


def _font_px(chunk: str, default: float) -> float:
    for m in re.finditer(r"font-size\s*[:=]\s*\"?\s*([\d.]+)\s*(px|pt|em|rem|%)?", chunk):
        v, unit = float(m.group(1)), m.group(2) or ""
        if unit == "pt":
            return v * 96 / 72
        if unit in ("em", "rem"):
            return v * default
        if unit == "%":
            return v * default / 100
        if v >= 4:
            return v
    return default


def svg_texts(svg: str, kind: str) -> list[TextRun]:
    """Every run of text in the rendered SVG, with its role, font size and width.

    One pass over <g>, <text> and <foreignObject> tokens keeps the enclosing group classes in
    view, which is how a note is told from a node label when both are html labels."""
    default = DEFAULT_FONT_PX if kind != "graphviz" else 14.0
    m = re.search(r"<style>[^<]*?font-size\s*:\s*([\d.]+)px", svg)
    if m:
        default = float(m.group(1))
    runs: list[TextRun] = []
    stack: list[str] = []

    def context() -> str:
        for gcls in reversed(stack):
            if re.search(r"\bnote\b|\bnoteText\b|\bnoteLabel\b", gcls):
                return "note"
            if re.search(r"\bedgeLabel\b|\bedgePath\b|\bedge\b|\bmessageText\b", gcls):
                return "edge"
            if re.search(r"\bmembers\b|\bclassMember\b|\battributeBox\b", gcls):
                return "member"
            if re.search(r"\bnode\b|\bcluster\b|\bactor\b|\bstate\b|\bentity\b|\bstatediagram-state\b|\blegend\b", gcls):
                return "node"
        return ""

    # attributes are read by name, never by position: a renderer is free to reorder them
    token = re.compile(r"<g\b([^>]*)>|</g>|<text\b([^>]*)>(.*?)</text>|<foreignObject\b([^>]*)>(.*?)</foreignObject>", re.S)
    for tok in token.finditer(svg):
        if tok.group(0) == "</g>":
            if stack:
                stack.pop()
            continue
        if tok.group(0).startswith("<g"):
            cm = re.search(r'class="([^"]*)"', tok.group(1) or "")
            dm = re.search(r'data-id="([^"]*)"', tok.group(1) or "")
            # a class-diagram note is marked only by its data-id (edgeNote0), not a class
            stack.append((cm.group(1) if cm else "") + (" note" if dm and "note" in dm.group(1).lower() else ""))
            continue
        if tok.group(0).startswith("<foreignObject"):
            fo_attrs, chunk = tok.group(4) or "", tok.group(5) or ""
            text = strip_markup(re.sub(r"<br\s*/?>", " ", chunk))
            if not text:
                continue
            cls = " ".join(re.findall(r'class="([^"]*)"', chunk))
            ctx = context()
            role = ctx if ctx in ("note", "member") else _role(cls + " " + " ".join(stack[-2:]), ctx or "node")
            px = _font_px(chunk, default)
            wm = re.search(r'\bwidth="([\d.]+)"', fo_attrs)
            width = float(wm.group(1)) if wm else 0.0
            if width <= 0:
                width = len(text) * px * CHAR_WIDTH_EM
            runs.append(TextRun(role, text, px, width, bool(wm) and float(wm.group(1)) > 0))
            continue
        attrs, inner = tok.group(2) or "", tok.group(3) or ""
        text = strip_markup(inner)
        if not text:
            continue
        cls = " ".join(re.findall(r'class="([^"]*)"', attrs + inner))
        ctx = context()
        role = ctx if ctx == "note" else _role(cls + " " + " ".join(stack[-2:]), ctx)
        if kind == "gantt" and role == "other":
            role = "axis"
        px = _font_px(attrs + inner, default)
        wm = re.search(r"width-([\d.]+)", cls)
        # a wrapped <text> is as wide as its widest <tspan> line, not the sum of its lines
        width = float(wm.group(1)) if wm else max(len(l) for l in svg_lines(inner)) * px * CHAR_WIDTH_EM
        runs.append(TextRun(role, text, px, width, bool(wm)))
    return runs


def measure_svg(svg_path: Path, kind: str) -> tuple[float, float, list[TextRun], list[str]]:
    svg = svg_path.read_text(encoding="utf-8", errors="replace")
    w = h = 0.0
    m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', svg)
    if m:
        w, h = float(m.group(1)), float(m.group(2))
    else:
        mw = re.search(r'width="([\d.]+)(pt|px)?', svg)
        mh = re.search(r'height="([\d.]+)(pt|px)?', svg)
        w = float(mw.group(1)) * (96 / 72 if mw and mw.group(2) == "pt" else 1) if mw else 0.0
        h = float(mh.group(1)) * (96 / 72 if mh and mh.group(2) == "pt" else 1) if mh else 0.0
    return w, h, svg_texts(svg, kind), layout_defects(svg, kind)


# ----------------------------------------------------------------- layout: what a reader sees first

LAYOUT_CHAR_EM = 0.42      # a true lower bound on average glyph width (identifiers run narrow); a flagged overflow is real
LAYOUT_SLACK_PX = 4.0      # ignore crossings and overflows smaller than this
MESSAGE_ROW_PX = 45.0     # a sequence message's text sits ~29px above its arrow; 45 leaves slack
PAGE_HEIGHT_PX = 864       # 9in at 96dpi: a printed page inside its margins, about one screen
SEQ_ACTOR_W = 150          # mermaid's default actor box width (a render config may override it)
SEQ_ACTOR_MARGIN = 50      # mermaid's default gap between actor boxes (the magazine's config sets its own)
SEQ_MARGIN = 100           # the 50px the renderer leaves either side of the diagram


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return m.group(1) if m else None


def _layout_default_font(svg: str, kind: str) -> float:
    """The base font size a layout check falls back to when a run gives none of its own."""
    default = DEFAULT_FONT_PX if kind != "graphviz" else 14.0
    m = re.search(r"<style>[^<]*?font-size\s*:\s*([\d.]+)px", svg)
    return float(m.group(1)) if m else default


def layout_defects(svg: str, kind: str) -> list[str]:
    """Text a lifeline runs through, and text that leaves a fixed box. Positions come from the
    SVG geometry exactly; glyph widths are estimated low, so a finding is a defect a reader
    would see and a clean result is not a guarantee. Mermaid sizes every box it draws — nodes,
    actors, notes — to the text, so overflow there is structurally impossible and is not
    claimed; it is checked where a box can be fixed: Graphviz nodes (fixedsize, width).

    Two unrelated checks live behind this one entry point because a caller only ever wants
    "does this diagram have a layout defect", never one algorithm by name; each kind runs at
    most one of them."""
    default = _layout_default_font(svg, kind)
    if kind == "sequence":
        return _layout_defects_sequence(svg, default)
    if kind == "graphviz":
        return _layout_defects_graphviz(svg, default)
    return []


def _layout_defects_sequence(svg: str, default: float) -> list[str]:
    """A message's text against every actor lifeline and its own arrow: struck-through,
    spanning a lifeline it does not touch, or centred on the sender's own line."""
    out: list[str] = []

    def est(text: str, px: float) -> float:
        return len(text) * px * LAYOUT_CHAR_EM

    lifelines = sorted(float(_attr(a, "x1") or 0) for a in re.findall(r"<line\b([^>]*)>", svg) if "actor-line" in a)
    # every message's arrow: a <line x1 x2 y1> between two actors, or a <path d="M x,y C…">
    # loop back to the same actor. The text sits a fixed distance above its own arrow, so the
    # arrow is found by row: the nearest one below the text whose span covers the text's x.
    # (Matching on the midpoint failed: the arrowhead shortens the line, the text lands a few
    # px off centre, and without the row a neighbouring arrow could be taken for this one.)
    arrows: list[tuple[float, float, bool, float]] = []
    for tag, attrs in re.findall(r"<(line|path)\b([^>]*)>", svg):
        if "messageLine" not in (_attr(attrs, "class") or ""):
            continue
        if tag == "line":
            arrows.append((float(_attr(attrs, "x1") or 0), float(_attr(attrs, "x2") or 0), False,
                           float(_attr(attrs, "y1") or 0)))
        else:
            mm = re.match(r"\s*M\s*([\d.\-]+)[ ,]+([\d.\-]+)", _attr(attrs, "d") or "")
            if mm:
                arrows.append((float(mm.group(1)), float(mm.group(1)), True, float(mm.group(2))))
    for attrs, inner in re.findall(r"<text\b([^>]*)>(.*?)</text>", svg, re.S):
        cls, text = _attr(attrs, "class") or "", strip_markup(inner)
        if not text or "messageText" not in cls:
            continue
        x = float(_attr(attrs, "x") or 0)
        px = _font_px(attrs + inner, default)
        w = est(text, px)
        lo, hi = x - w / 2, x + w / 2
        y = float(_attr(attrs, "y") or 0)
        below = [a for a in arrows if y < a[3] <= y + MESSAGE_ROW_PX
                 and min(a[0], a[1]) - 8 <= x <= max(a[0], a[1]) + 8]
        arrow = min(below, key=lambda a: a[3] - y) if below else None
        if arrow and arrow[2]:
            # a self-message: mermaid centres the text on the actor's own lifeline, so the
            # line runs through it at any length — a warning, with the way out
            out.append(f"self-message-struck: \"{text[:60]}\" sits on its own lifeline, which mermaid draws "
                       f"through the text at any length; a `Note right of` beside the loop reads cleanly")
            continue
        span = (min(arrow[0], arrow[1]), max(arrow[0], arrow[1])) if arrow else (x, x)
        between = [lx for lx in lifelines if span[0] + 1 < lx < span[1] - 1]
        if between:
            # certain, no estimate involved: the text is centred on a lifeline it does not touch.
            # Structural, like the self-message: only participant order or messageAlign changes it
            out.append(f"spanning-struck: message \"{text[:60]}\" spans {len(between) + 1} gaps and is centred on "
                       f"the lifeline between, which runs through the text; put the participants that talk "
                       f"side by side, or set sequence.messageAlign to left where the surface allows a directive")
            continue
        crossed = [lx for lx in lifelines if lo + LAYOUT_SLACK_PX < lx < hi - LAYOUT_SLACK_PX]
        if crossed:
            out.append(f"struck-through: message \"{text[:60]}\" is wider than the gap it sits in; "
                       f"{len(crossed)} lifeline(s) run through the text")
    return out


def _layout_defects_graphviz(svg: str, default: float) -> list[str]:
    """Inside each node group, the widest text against the widest shape: a fixed-size Graphviz
    box the label does not fit in."""
    out: list[str] = []

    def est(text: str, px: float) -> float:
        return len(text) * px * LAYOUT_CHAR_EM

    token = re.compile(r"<g\b([^>]*)>|</g>|<rect\b([^>]*)/?>|<polygon\b([^>]*)/?>|<ellipse\b([^>]*)/?>|<text\b([^>]*)>(.*?)</text>|<foreignObject\b([^>]*)>(.*?)</foreignObject>", re.S)
    stack: list[dict | None] = []
    for tok in token.finditer(svg):
        s = tok.group(0)
        if s == "</g>":
            if stack:
                rec = stack.pop()
                if rec and rec["box"] > 0 and rec["text"] and rec["text"][0] > rec["box"] + LAYOUT_SLACK_PX:
                    out.append(f"overflow: label \"{rec['text'][1][:60]}\" ({rec['text'][0]:.0f}px) is wider than its "
                               f"{rec['box']:.0f}px shape")
            continue
        if s.startswith("<g"):
            cls = _attr(tok.group(1) or "", "class") or ""
            stack.append({"box": 0.0, "text": None} if re.search(r"\bnode\b", cls) else None)
            continue
        rec = next((r for r in reversed(stack) if r is not None), None)
        if rec is None:
            continue
        if s.startswith("<rect"):
            rec["box"] = max(rec["box"], float(_attr(tok.group(2) or "", "width") or 0))
        elif s.startswith("<polygon"):
            xs = [float(p.split(",")[0]) for p in (_attr(tok.group(3) or "", "points") or "").split() if "," in p]
            if xs:
                rec["box"] = max(rec["box"], max(xs) - min(xs))
        elif s.startswith("<ellipse"):
            rec["box"] = max(rec["box"], 2 * float(_attr(tok.group(4) or "", "rx") or 0))
        elif s.startswith("<text"):
            # a wrapped label is several <tspan> lines; the widest line is what must fit
            for line in svg_lines(tok.group(6) or ""):
                w = est(line, _font_px((tok.group(5) or "") + (tok.group(6) or ""), default))
                if rec["text"] is None or w > rec["text"][0]:
                    rec["text"] = (w, line)
        elif s.startswith("<foreignObject"):
            text = strip_markup(tok.group(8) or "")
            wm = _attr(tok.group(7) or "", "width")
            if text and wm and float(wm) > 0:
                w = float(wm)
                if rec["text"] is None or w > rec["text"][0]:
                    rec["text"] = (w, text)
    return out


# ----------------------------------------------------------------- judgement

def _check_target_mechanics(rep: DiagramReport, src: str, target: str) -> None:
    """Will it render where it has to live: ADO-specific breakage only."""
    if target != "ado":
        return
    bad = sorted({hx for hx in HEX_COLOR.findall(src) if not re.search(r"[A-Fa-f]", hx[1:])})
    if bad:
        rep.add("blocker", "ado-hex",
                f"{', '.join(bad)} digit-only; Azure DevOps substitutes #<digits> as a "
                f"work-item mention inside mermaid and corrupts the diagram")
    if INIT_DIRECTIVE.search(src):
        rep.add("nit", "ado-init",
                "%%{init}%% is rejected by ADO's mermaid; fine if an embed pipeline "
                "strips it before publishing, otherwise move styling to classDef")


def _check_init_directive(rep: DiagramReport, src: str) -> None:
    """A %%{init}%% directive that mermaid itself cannot parse, regardless of target."""
    im = INIT_DIRECTIVE.search(src)
    if not im:
        return
    close = src.find("}%%", im.start())
    if close < 0:
        rep.add("blocker", "init-unterminated", "a %%{init} directive with no closing }%% — whatever the renderer makes of it is not what was meant")
    elif "\n" in src[im.start(): close + 3]:
        rep.add("warning", "init-multiline", "a %%{init}%% directive spanning lines is a parse error in mermaid")


def _check_parse_status(rep: DiagramReport) -> None:
    if not rep.parsed:
        rep.add("warning", "unparsed",
                f"the tool does not extract entities from a {rep.kind} diagram; node and edge "
                f"counts are not available and a redraw cannot be verified by diff — verify by eye")


def _check_render_status(rep: DiagramReport, render_error: str) -> bool:
    """False means the caller must stop: nothing past this point can be measured."""
    if not rep.rendered:
        rep.add("blocker", "no-render", f"the diagram does not render{': ' + render_error if render_error else ''}")
        return False
    return True


def _check_measure_status(rep: DiagramReport) -> bool:
    """The gate fails closed: a render that could not be measured is refused, not passed."""
    if rep.measure_error:
        rep.add("blocker", "unmeasured",
                f"rendered, but legibility could not be measured: {rep.measure_error} — no verdict; "
                f"measure by eye or fix the renderer before trusting this diagram")
        return False
    return True


# A title that names only the kind of picture tells the reader nothing the picture does not.
GENERIC_TITLE = re.compile(
    r"^(?:(?:figure|fig\.?|diagram|chart|graph|image|picture)\s*\d*|"
    r"(?:the\s+)?(?:flow\s*chart|flowchart|flow|overview|architecture|sequence(?:\s+diagram)?|"
    r"class\s+diagram|state\s+diagram|er\s+diagram|data\s+model|process|workflow))\s*[:.]?$",
    re.I)
TITLE_MIN_WORDS = 3        # fewer is a label, not a statement of what the diagram shows


def _check_title_and_caption(rep: DiagramReport) -> None:
    """A figure in a document says what it is (a title) and what it shows (a caption); a reader
    should never have to work out from the picture what it is a picture of."""
    if not rep.in_document:
        return
    if not rep.title:
        rep.add("blocker", "untitled",
                "no title: put one bold line just above the diagram that names what the reader "
                "learns from it (\"How a work item moves from triage to done\")")
    elif GENERIC_TITLE.match(rep.title) or words(rep.title) < TITLE_MIN_WORDS:
        rep.add("blocker", "generic-title",
                f"title \"{rep.title}\" names the kind of picture, not what it shows; say what "
                f"the reader learns from it, in {TITLE_MIN_WORDS} words or more")
    if not rep.caption:
        rep.add("blocker", "uncaptioned",
                f"no caption: put one italic line just below the diagram, under "
                f"{fences.CAPTION_MAX_WORDS + 1} words, saying what it shows")
    elif words(rep.caption) > fences.CAPTION_MAX_WORDS:
        rep.add("blocker", "long-caption",
                f"caption is {words(rep.caption)} words; keep it under {fences.CAPTION_MAX_WORDS + 1} "
                f"— the title and prose carry the rest")
    elif rep.title and rep.caption.strip(" .").lower() == rep.title.strip(" .").lower():
        rep.add("warning", "caption-repeats-title",
                "the caption repeats the title; say what the reader sees in the diagram instead")


def _check_legibility(rep: DiagramReport, target: str) -> None:
    """Legibility, the thing that costs him manual labour."""
    if rep.label_pt_at_target < LABEL_FLOOR_PT:
        rep.add("blocker", "illegible",
                f"labels print at {rep.label_pt_at_target:.1f}pt {_surface(target, rep)}; floor is {LABEL_FLOOR_PT}pt")
    elif rep.label_pt_at_target < LABEL_TARGET_PT:
        rep.add("warning", "tight",
                f"labels print at {rep.label_pt_at_target:.1f}pt; target is {LABEL_TARGET_PT}pt")


def _check_structural_floor(rep: DiagramReport, target: str) -> None:
    """The real constraint, said up front: geometry no label can change."""
    if rep.structural_reason and rep.structural_pt < LABEL_FLOOR_PT:
        rep.add("blocker", "needs-author",
                f"{rep.structural_reason} fix a minimum width before any label is written: {_surface(target, rep)}, "
                f"the best possible label is {rep.structural_pt:.1f}pt, under the {LABEL_FLOOR_PT}pt floor; "
                f"shortening labels cannot help — split by a boundary a reader would recognise")
    elif rep.parsed and rep.nodes > NODE_BUDGET and rep.label_pt_at_target < LABEL_FLOOR_PT:
        rep.add("blocker", "needs-author",
                f"{rep.nodes} nodes and illegible: split first, labels second — past ~{NODE_BUDGET} nodes "
                f"shortening labels does not bring a diagram back over the floor")


def _check_height(rep: DiagramReport, target: str) -> None:
    """Height: five screens of diagram is not read either."""
    if rep.height_at_target_px > 3 * PAGE_HEIGHT_PX:
        rep.add("blocker", "tall",
                f"{rep.height_at_target_px:.0f}px tall {_surface(target, rep)}, {rep.height_at_target_px / PAGE_HEIGHT_PX:.1f} "
                f"pages of {PAGE_HEIGHT_PX}px; nobody scrolls a figure — split it")
    elif rep.height_at_target_px > 1.5 * PAGE_HEIGHT_PX:
        rep.add("warning", "tall",
                f"{rep.height_at_target_px:.0f}px tall {_surface(target, rep)}, {rep.height_at_target_px / PAGE_HEIGHT_PX:.1f} "
                f"pages of {PAGE_HEIGHT_PX}px; a reader sees it in pieces")


def _check_layout_defect_findings(rep: DiagramReport) -> None:
    """What a reader notices in the first two seconds."""
    for defect in rep.layout_defects:
        code = defect.split(":")[0]
        rep.add("warning" if code in ("self-message-struck", "spanning-struck") else "blocker", code,
                defect.split(": ", 1)[1] if ": " in defect else defect)


def _check_width_exhausted(rep: DiagramReport) -> None:
    """When the label rule has nothing left to give, say so: shorter labels will not fix it."""
    d = rep.width_driver
    already = any(f.code == "needs-author" for f in rep.findings)
    if rep.label_pt_at_target < LABEL_FLOOR_PT and d and not already:
        if d["role"] == "member":
            rep.add("blocker", "needs-author",
                    f"illegible, and the width is set by a member ({d['words']} words): members are content, "
                    f"not labels — the author must decide whether to split the diagram or shorten the members")
        elif rep.max_label_words <= MAX_LABEL_WORDS and rep.max_edge_words <= MAX_LABEL_WORDS:
            rep.add("blocker", "needs-author",
                    f"illegible with every label already within {MAX_LABEL_WORDS} words: the label rule cannot help; "
                    f"this needs a split{', a change of type' if rep.parsed and rep.nodes > NODE_BUDGET else ''} or the author's decision")


def _check_width_driver_nit(rep: DiagramReport) -> None:
    """What drives the width: the fix has to aim at this, not at node labels by reflex."""
    d = rep.width_driver
    if d and rep.label_pt_at_target < LABEL_TARGET_PT:
        rep.add("nit", "width-driver",
                f"the widest text is a {d['role']} label of {d['words']} words "
                f"({'measured' if d['measured'] else 'estimated'} {d['width_px']:.0f}px): "
                f"\"{d['text'][:80]}\" — shorten that, not the font")


def _check_long_notes(rep: DiagramReport) -> None:
    """A note is prose by design, but a paragraph in a note belongs in the document."""
    if rep.long_notes:
        rep.add("warning", "long-note",
                f"{len(rep.long_notes)} note(s) over {NOTE_MAX_WORDS} words; a note is a caption, a paragraph goes in the prose")


def _check_label_bloat(rep: DiagramReport) -> None:
    """Label bloat, which is the usual cause of illegibility above."""
    if rep.max_label_words > MAX_LABEL_WORDS and rep.kind != "pie":   # a pie's labels are a legend list; they widen nothing
        rep.add("warning", "verbose-labels",
                f"{len(rep.long_labels)} node label(s) over {MAX_LABEL_WORDS} words "
                f"(longest {rep.max_label_words}); long labels widen nodes, and width is "
                f"what forces the render to shrink")
    if rep.max_edge_words > MAX_LABEL_WORDS:
        rep.add("warning", "verbose-edge-labels",
                f"{len(rep.long_edge_labels)} edge/message label(s) over {MAX_LABEL_WORDS} words "
                f"(longest {rep.max_edge_words}); an edge carries a verb, not a sentence")


def _check_size_and_type_fit(rep: DiagramReport) -> None:
    """Size and type fit, only where the graph was actually read."""
    if rep.parsed and rep.nodes > NODE_BUDGET:
        rep.add("warning", "oversized",
                f"{rep.nodes} nodes; past ~{NODE_BUDGET} an overview should split into "
                f"<thing>-overview plus one file per subprocess")
    if rep.parsed and rep.kind == "flowchart" and rep.nodes >= 5:
        if rep.back_edges and rep.multi_parent_nodes >= 2:
            rep.add("warning", "type-fit",
                    f"declared a flowchart but has {rep.back_edges} back-edge(s) and "
                    f"{rep.multi_parent_nodes} nodes with several inbound edges — that is a "
                    f"graph, not a flow; Graphviz lays it out far better")
        elif rep.direction in ("LR", "RL") and rep.nodes > 8:
            rep.add("nit", "direction",
                    f"{rep.nodes} nodes left-to-right will be wide and shrink; top-down is "
                    f"usually taller and more legible — unless the nodes come in pairs")


def assess(rep: DiagramReport, src: str, target: str, render_error: str) -> None:
    """Run every finding rule for one diagram, in the order a reader would hit the problems:
    can it render where it lives, can it even be measured, then legibility, size and type fit.
    Each rule is its own small function; this is just their call order."""
    _check_target_mechanics(rep, src, target)
    _check_init_directive(rep, src)
    _check_title_and_caption(rep)
    _check_parse_status(rep)
    if not _check_render_status(rep, render_error):
        return
    if not _check_measure_status(rep):
        return
    _check_legibility(rep, target)
    _check_structural_floor(rep, target)
    _check_height(rep, target)
    _check_layout_defect_findings(rep)
    _check_width_exhausted(rep)
    _check_width_driver_nit(rep)
    _check_long_notes(rep)
    _check_label_bloat(rep)
    _check_size_and_type_fit(rep)


def _ranks(g: Graph) -> dict[str, int]:
    out: dict[str, list[str]] = {}
    inbound: dict[str, int] = {n: 0 for n in g.nodes}
    for a, b, _ in g.edges:
        if a == b:
            continue
        out.setdefault(a, []).append(b)
        inbound[b] = inbound.get(b, 0) + 1
        inbound.setdefault(a, 0)
    rank: dict[str, int] = {}
    frontier = [n for n, c in inbound.items() if c == 0] or list(g.nodes)[:1]
    for n in frontier:
        rank[n] = 0
    while frontier:
        nxt = []
        for n in frontier:
            for m in out.get(n, []):
                if m not in rank:
                    rank[m] = rank[n] + 1
                    nxt.append(m)
        frontier = nxt
    for n in g.nodes:
        rank.setdefault(n, 0)
    return rank


def _sequence_geometry(config: dict) -> tuple[float, float, float]:
    """(actor width, actor gap, font px) a sequence diagram is drawn with under `config`;
    mermaid's defaults when the config leaves them unset."""
    seq = config.get("sequence", {})
    font = str(config.get("themeVariables", {}).get("fontSize", DEFAULT_FONT_PX)).removesuffix("px")
    try:
        font_px = float(font)
    except ValueError:
        font_px = DEFAULT_FONT_PX
    return float(seq.get("width", SEQ_ACTOR_W)), float(seq.get("actorMargin", SEQ_ACTOR_MARGIN)), font_px


def analyse(path: Path, target: str, workdir: Path, kind: str | None = None) -> list[DiagramReport]:
    """kind: the magazine edition kind (feature, brief, dashboard) whose placement rules measure
    the magazine target; None lets the builder use its default."""
    reports: list[DiagramReport] = []
    config_file, config, config_error = None, {}, ""
    if target == "magazine":
        if not MAGAZINE_BUILD.exists():
            raise SystemExit(f"audit.py: the magazine target needs the magazine skill beside this one ({MAGAZINE_BUILD} is missing)")
        config_file, config, config_error = magazine_mermaid_config(workdir)
    actor_w, actor_gap, font_px = _sequence_geometry(config)
    labels = figure_labels(path)
    for index, src, fenced in extract_diagrams(path):
        if not src.strip():
            continue
        rep = DiagramReport(path=str(path), index=index)
        if labels is not None:
            rep.in_document = True
            rep.title, rep.caption = labels[index]
        if fenced:
            rep.add("warning", "fenced-mmd",
                    "a .mmd holds raw mermaid source; this one is wrapped in a markdown "
                    "fence, which the contract forbids and the embed pipeline does not expect")
        rep.kind, rep.direction = detect_kind(src)
        g = parse_graph(src, rep.kind)
        rep.parsed = g.parsed
        if g.parsed:
            rep.nodes, rep.edges = len(g.nodes), len(g.edges)
            rep.node_labels = sorted(set(v for v in g.nodes.values() if v))
            # A back-edge points from a deeper rank to a shallower one, ranks taken by breadth-first
            # walk from the sources. Declaration order would call a decision tree whose branches
            # converge on an error node declared early a graph; rank does not.
            rank = _ranks(g)
            rep.back_edges = sum(1 for a, b, _ in g.edges if a != b and rank.get(b, 0) < rank.get(a, 0))
            inbound: dict[str, int] = {}
            for _, b, _ in g.edges:
                inbound[b] = inbound.get(b, 0) + 1
            rep.multi_parent_nodes = sum(1 for c in inbound.values() if c >= 2)

        # label words from the source graph, then from the render (which sees every type)
        node_texts = [v for v in g.nodes.values() if v] if g.parsed else []
        edge_texts = [l for _, _, l in g.edges if l] if g.parsed else []

        # geometry the labels cannot change: n sequence participants are n fixed boxes and gaps
        min_w, structural_reason = 0, ""
        if g.parsed and rep.kind == "sequence" and len(g.nodes) >= 2 and not re.search(r"actorMargin|\"width\"|'width'|\bwrap\b", src):
            n = len(g.nodes)
            min_w = round(n * actor_w + (n - 1) * actor_gap + SEQ_MARGIN)
            structural_reason = f"{n} participants ({actor_w:g}px boxes, {actor_gap:g}px gaps: {min_w}px)"
            if target != "magazine":
                rep.structural_pt = font_px * 0.75 * min(1.0, (TARGETS[target] * 96.0) / min_w)
                rep.structural_reason = structural_reason

        stem = f"{path.stem}-{index}"[:60].replace(" ", "_")
        if config_error and rep.kind != "graphviz":
            svg, err = None, config_error      # fail closed: never measure the magazine with another config
        else:
            svg, err = render_svg(src, rep.kind, workdir, stem, config_file)
        if svg:
            rep.rendered = True
            rep.native_w, rep.native_h, runs, rep.layout_defects = measure_svg(svg, rep.kind)
            rep.text_runs = len(runs)
            if target != "magazine":
                scale = min(1.0, (TARGETS[target] * 96.0) / rep.native_w) if rep.native_w else 1.0
            else:
                # The magazine fits a plate to the page height as well as the width, and picks
                # among column, tall, turned and landscape placements: its scale is what prints.
                scale = 1.0
                if rep.native_w and rep.native_h:
                    placement, place_error = magazine_placement(rep.native_w, rep.native_h, kind)
                    if placement:
                        scale = placement["scale"]
                        rep.placement = placement["cls"]
                    else:
                        rep.measure_error = place_error   # fail closed, like the config above
                if min_w and rep.native_h:
                    # The best case: every message shortened until the participants alone set
                    # the width, placed as the builder would place that narrower figure.
                    best, _ = magazine_placement(min_w, rep.native_h, kind)
                    if best:
                        rep.structural_pt = font_px * 0.75 * best["scale"]
                        rep.structural_reason = structural_reason
            rep.height_at_target_px = rep.native_h * scale
            label_runs = [r for r in runs if r.role in ("node", "edge", "member")]
            # fail closed: no width, or text the tool cannot place in a role, is not a pass
            if not rep.native_w or not rep.native_h:
                rep.measure_error = "the SVG declares no width or viewBox to scale from"
            elif not label_runs:
                rep.measure_error = (f"none of the {len(runs)} text runs could be identified as a node, edge or member label"
                                     if runs else "the render holds no text at all")
            if label_runs:
                rep.label_pt_at_target = min(r.px for r in label_runs) * 0.75 * scale
            if runs:
                rep.smallest_text_pt = min(r.px for r in runs) * 0.75 * scale
                cands = label_runs or runs
                widest = max(cands, key=lambda r: r.width_px)
                rep.width_driver = {"role": widest.role, "text": widest.text, "words": words(widest.text),
                                    "width_px": widest.width_px, "measured": widest.measured}
            node_texts += [r.text for r in runs if r.role in ("node", "member")]
            edge_texts += [r.text for r in runs if r.role == "edge"]
            rep.long_notes = sorted({r.text for r in runs if r.role == "note" and words(r.text) > NOTE_MAX_WORDS}
                                    | {t for t in g.notes if words(t) > NOTE_MAX_WORDS})

        node_texts = sorted(set(node_texts))
        edge_texts = sorted(set(edge_texts))
        counts = sorted(words(v) for v in node_texts)
        if counts:
            rep.max_label_words = counts[-1]
            rep.median_label_words = counts[len(counts) // 2]
            rep.long_labels = [v for v in node_texts if words(v) > MAX_LABEL_WORDS]
        ecounts = [words(v) for v in edge_texts]
        if ecounts:
            rep.max_edge_words = max(ecounts)
            rep.long_edge_labels = [v for v in edge_texts if words(v) > MAX_LABEL_WORDS]
        assess(rep, src, target, err)
        reports.append(rep)
    return reports


# ----------------------------------------------------------------- commands

def _is_fixture(path: Path) -> bool:
    return any(part.lower() in FIXTURE_DIRS for part in path.parts)


def cmd_audit(args: argparse.Namespace) -> int:
    root = Path(args.path)
    files = (
        [root] if root.is_file()
        else [p for ext in ("*.mmd", "*.mermaid", "*.md", "*.dot", "*.gv") for p in root.rglob(ext)]
    )
    skipped = 0
    kept = []
    for p in files:
        if not args.include_fixtures and _is_fixture(p):
            skipped += 1
            continue
        if any(fnmatch.fnmatch(str(p), pat) or pat in str(p) for pat in (args.exclude or [])):
            skipped += 1
            continue
        kept.append(p)
    files = kept[: args.limit]
    if skipped:
        print(f"  skipped {skipped} file(s) in fixture, test-data or excluded directories "
              f"(--include-fixtures to audit them; they are written to fail)", file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="diagram-audit-") as tmp:
        workdir = Path(tmp)
        all_reports: list[DiagramReport] = []
        for n, path in enumerate(files, 1):
            try:
                found = analyse(path, args.target, workdir, args.kind)
            except Exception as exc:  # a broken file is a finding, not a crash
                rep = DiagramReport(path=str(path))
                rep.add("blocker", "audit-error", f"{type(exc).__name__}: {exc}")
                found = [rep]
            all_reports.extend(found)
            if found and args.verbose:
                for r in found:
                    print(f"  [{r.worst:8s}] {Path(r.path).name}#{r.index} "
                          f"{r.kind}/{r.direction or '-'} n={r.nodes if r.parsed else '?'} "
                          f"pt={r.label_pt_at_target:.1f} {len(r.findings)} finding(s)")
            if n % 25 == 0:
                print(f"  ... {n}/{len(files)} files", file=sys.stderr)

    total = len(all_reports)
    by_worst = {k: sum(1 for r in all_reports if r.worst == k) for k in ("blocker", "warning", "nit", "clean")}
    by_kind: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for r in all_reports:
        by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
        for f in r.findings:
            by_code[f.code] = by_code.get(f.code, 0) + 1

    legible = [r for r in all_reports if r.rendered and r.label_pt_at_target]
    print(f"\n=== {total} diagrams in {len(files)} files, target {args.target} ({_surface(args.target)}) ===")
    print(f"  worst finding : {by_worst}")
    print(f"  by type       : {dict(sorted(by_kind.items(), key=lambda kv: -kv[1]))}")
    print(f"  rendered      : {sum(1 for r in all_reports if r.rendered)}/{total}   "
          f"parsed: {sum(1 for r in all_reports if r.parsed)}/{total}")
    if legible:
        pts = sorted(r.label_pt_at_target for r in legible)
        print(f"  label pt      : min {pts[0]:.1f}  median {pts[len(pts)//2]:.1f}  max {pts[-1]:.1f}   "
              f"below {LABEL_FLOOR_PT}pt: {sum(1 for p in pts if p < LABEL_FLOOR_PT)}")
        drivers: dict[str, int] = {}
        for r in legible:
            if r.width_driver and r.label_pt_at_target < LABEL_TARGET_PT:
                drivers[r.width_driver["role"]] = drivers.get(r.width_driver["role"], 0) + 1
        if drivers:
            print(f"  width driven by: {dict(sorted(drivers.items(), key=lambda kv: -kv[1]))} (where under target)")
    lab = sorted(r.max_label_words for r in all_reports if r.max_label_words)
    if lab:
        worst = max(all_reports, key=lambda r: r.max_label_words)
        print(f"  node label words: median-max {lab[len(lab)//2]}  worst {lab[-1]} ({Path(worst.path).name})  "
              f"diagrams over {MAX_LABEL_WORDS}: {sum(1 for v in lab if v > MAX_LABEL_WORDS)}")
    elab = sorted(r.max_edge_words for r in all_reports if r.max_edge_words)
    if elab:
        print(f"  edge label words: median-max {elab[len(elab)//2]}  worst {elab[-1]}  "
              f"diagrams over {MAX_LABEL_WORDS}: {sum(1 for v in elab if v > MAX_LABEL_WORDS)}")
    print(f"  findings      : {dict(sorted(by_code.items(), key=lambda kv: -kv[1]))}")

    if args.json:
        Path(args.json).write_text(json.dumps([asdict(r) for r in all_reports], indent=1), encoding="utf-8")
        print(f"\n  wrote {args.json}")
    return 0


def graphs_of(path: Path) -> list[Graph]:
    out = []
    for _index, src, _fenced in extract_diagrams(path):
        if not src.strip():
            continue
        kind, _ = detect_kind(src)
        g = parse_graph(src, kind)
        g.title = diagram_title(src)
        out.append(g)
    return out


def cmd_graph(args: argparse.Namespace) -> int:
    path = Path(args.path)
    for index, g in enumerate(graphs_of(path)):
        print(json.dumps({
            "file": str(path), "index": index, "kind": g.kind, "parsed": g.parsed, "note": g.note,
            "nodes": g.nodes,
            "edges": [{"from": a, "to": b, "label": l} for a, b, l in g.edges],
            "members": g.members,
            "notes": g.notes,
        }, indent=1))
    return 0


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", strip_markup(s).lower()).strip()


def _merge(graphs: list[Graph]) -> Graph:
    g = Graph(graphs[0].kind if graphs else "unknown", all(x.parsed for x in graphs) and bool(graphs))
    for x in graphs:
        if not x.parsed:
            g.note = x.note
        g.title = " ".join(filter(None, [g.title, x.title]))
        if x.kind not in ID_KINDS:
            # generated ids (n0, n1…) collide across the files of a split: key by the label
            key = {k: _norm(v or k) for k, v in x.nodes.items()}
            g.nodes.update({key[k]: v for k, v in x.nodes.items()})
            g.edges.extend((key.get(a, a), key.get(b, b), l) for a, b, l in x.edges)
            g.notes.extend(x.notes)
            for k, v in x.members.items():   # a pie's value, a gantt's tags: keyed by label too
                g.members.setdefault(key.get(k, _norm(k)), []).extend(v)
            continue
        g.nodes.update(x.nodes)
        g.edges.extend(x.edges)
        g.notes.extend(x.notes)
        for k, v in x.members.items():
            g.members.setdefault(k, []).extend(v)
    return g


# Kinds whose entities carry authored ids that survive a redraw. For the others (a mindmap's
# topics, a gantt's tasks named in prose) the text is the identity.
ID_KINDS = {"flowchart", "graphviz", "sequence", "state", "class", "er", "c4", "gantt"}


ABBREVIATIONS = {"e.g", "i.e", "etc", "vs", "cf", "approx", "no"}   # prose, not identifiers
# A token cut short by an ellipsis is a prefix, not a fact: it is matched as a prefix.
TOKEN_RX = re.compile(r"([A-Za-z0-9/](?:[\w/-]|\.(?=\w))*)(\.\.\.|…)?")
PLACEHOLDER = re.compile(r"\{[^}]+\}|<[^>]+>|(?<=/):\w+|\.\.\.|…|\bN\b|\bXXX+\b")
SAMPLE_DIGITS = 4          # a bare number this long or longer is an example value, not a code


def _raw_tokens(s: str) -> list[str]:
    out = []
    for m in TOKEN_RX.finditer(strip_markup(s)):
        t = m.group(1).rstrip(".,;:-")
        if (len(t) > 1 or t.isdigit()) and t.lower() not in ABBREVIATIONS:
            out.append(t + "*" if m.group(2) else t)
    return out


def _tokens(s: str) -> set[str]:
    """Whole tokens plus their dot-parts and path segments, so `woDetail.Installer_ID` carries
    `Installer_ID` and a path carries each segment."""
    out: set[str] = set()
    for t in _raw_tokens(s):
        t = t.lower()
        out.add(t)
        for part in re.split(r"[./]", t.rstrip("*")):
            if len(part) > 1 or part.isdigit():
                out.add(part)
    return out


# Detail is what a reader would look up: a code or number, a path or URL, a slash-joined term
# (HTTP/HTTPS, DevOps/SRE), an acronym of three or more capitals, an identifier with an
# underscore, camelCase or a dot. Prose words may be reworded; these may only move.
def is_detail(t: str) -> bool:
    t = t.rstrip("*")
    return (any(c.isdigit() for c in t) or "/" in t or "_" in t
            or bool(re.fullmatch(r"[A-Z][A-Z0-9]{2,}", t))
            or bool(re.search(r"[a-z][A-Z]", t)) or bool(re.search(r"\w\.\w", t)))


def _detail_tokens(s: str) -> set[str]:
    """Detail tokens as written: case matters to the shared presence rule (a lower-case receiver
    may be dropped, a type qualifier may not); token_present compares case-blind."""
    return {t for t in _raw_tokens(s) if is_detail(t)}


def is_sample_value(t: str) -> bool:
    """A bare number of four or more digits (12345, 1985) is an example, not a fact a reader
    looks up; a status code or a state code is three digits or fewer and stays a fact."""
    return t.isdigit() and len(t) >= SAMPLE_DIGITS


def _flat(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _segments(path: str) -> list[str]:
    return [p for p in re.split(r"/", path.lower()) if p]


def _path_present(old: str, text: str) -> bool:
    """`/workorders/` is present in `/api/v2/workorders/{id}`, and so is `/api/v2/workorders/123`:
    the old path's segments in order, with a placeholder segment standing for any value."""
    want = _segments(old)
    if not want:
        return False
    for cand in re.findall(r"[\w.{}:<>…-]*/[\w./{}:<>…-]*", text):
        have = _segments(cand)
        for start in range(0, len(have) - len(want) + 1):
            if all(w == h or PLACEHOLDER.fullmatch(h) for w, h in zip(want, have[start:start + len(want)])):
                return True
    return False


def token_present(t: str, toks: set[str], text: str) -> bool:
    """Is the detail token `t` (as written; a trailing * marks an ellipsis-cut prefix) present in
    a piece of text, given its lower-case token set? Whole-token first; then a path by segments;
    then a prefix; then a dotted identifier by the shared presence rule; then an alias written as
    words (InternalAPI as Internal API)."""
    written, t = t, t.lower()
    if t.endswith("*"):
        return any(x.startswith(t[:-1]) for x in toks)
    if t in toks:
        return True
    if "/" in t and _path_present(t, text):
        return True
    if presence.member_present(written, text):
        return True
    if len(t) >= 5 and not any(c.isdigit() for c in t) and "/" not in t:
        return _flat(t) in _flat(text)
    return False


def visible_text(path: Path, near_figures: bool = True) -> str:
    """What a reader of this file can see outside the diagrams. For a .md, the prose of the
    section(s) that hold a diagram — from the heading before each fence to the next heading of
    the same or a higher level; a legend file passed explicitly is taken whole (near_figures
    False). Nothing for a .mmd/.gv: a %% comment is invisible in every render."""
    if path.suffix.lower() not in (".md", ".markdown", ".txt"):
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = fences.split_lines(text)
    heading = re.compile(r"^(#{1,6})\s")
    diagrams = [f for f in fences.scan(text) if f.diagram]
    inside = {i for f in diagrams for i in range(f.start, min(f.end + 1, len(lines)))}
    fence_at = [f.start for f in diagrams]
    keep = set(range(len(lines))) if (not near_figures or not fence_at) else set()
    for f in fence_at:
        level = 7
        start = 0
        for i in range(f, -1, -1):
            h = heading.match(lines[i])
            if h:
                level, start = len(h.group(1)), i
                break
        end = len(lines)
        for i in range(f + 1, len(lines)):
            h = heading.match(lines[i])
            if h and len(h.group(1)) <= level:
                end = i
                break
        # the section, and what sits directly beneath the figure even under its own heading:
        # a table or legend "beside the figure" is usually the next block
        keep.update(range(start, min(len(lines), max(end, f + NEAR_FIGURE_LINES))))
    out = [ln for i, ln in enumerate(lines) if i in keep and i not in inside]
    return "\n".join(out)


NEAR_FIGURE_LINES = 60     # lines after a fence that count as beside the figure

STOP_WORDS = {"the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is", "are", "with", "by", "at", "from", "as", "that", "this", "it", "its", "be", "not", "no", "per"}


def shares_context(line: str, old_label: str, new_label: str = "") -> bool:
    """A context line may carry a label's relocated detail only if it shares a word with the
    old label or the new one (a legend pairs the code with the label it now stands beside), or
    two of the old label's codes. "Throughput peaked at 204 requests" does not stand in for
    "200 OK / 204 No Content"."""
    lt = _tokens(line)
    plain_of = lambda s: {t for t in s if not is_detail(t) and t not in STOP_WORDS and len(t) > 2}
    if not plain_of(lt):
        return True        # a bare value on a line of its own (a response example) is that value
    plain = plain_of(_tokens(old_label) | _tokens(new_label))
    if plain & lt:
        return True
    # a label that is nothing but one identifier is its own context; a label with several codes
    # must be met by at least two of them
    detail = {t.lower() for t in _detail_tokens(old_label)}
    return len(detail & lt) >= min(2, len(detail)) > 0


def graph_text(g: Graph) -> str:
    return " ".join(list(g.nodes.values()) + [l for _, _, l in g.edges] + [m for v in g.members.values() for m in v] + [g.title] + g.notes)


# The title mermaid renders above a diagram (frontmatter `title:` or a `title` line) is visible
# to the reader and counts as diagram scope for relocated detail.
def diagram_title(src: str) -> str:
    m = re.search(r"^---\r?\n(.*?)\r?\n---", src, re.S)
    if m:
        t = re.search(r"^\s*title\s*:\s*(.+)$", m.group(1), re.M)
        if t:
            return t.group(1).strip().strip("\"'")
    t = re.search(r"^\s*title\s+(.+)$", strip_comments(src), re.M)
    return t.group(1).strip() if t else ""


def cmd_diff(args: argparse.Namespace) -> int:
    before = _merge(graphs_of(Path(args.before)))
    after = _merge([g for p in args.after for g in graphs_of(Path(p))])
    print(f"before: {args.before} ({before.kind}, {'parsed' if before.parsed else 'UNPARSED'})")
    print(f"after : {', '.join(args.after)} ({after.kind}, {'parsed' if after.parsed else 'UNPARSED'})")
    if not before.parsed or not after.parsed:
        print(f"VERDICT: UNVERIFIABLE — {before.note or after.note}")
        return 3

    by_id = before.kind in ID_KINDS and after.kind in ID_KINDS and before.kind == after.kind
    key = (lambda k, v: k) if by_id else (lambda k, v: _norm(v or k))
    b_key = {k: key(k, v) for k, v in before.nodes.items()}
    a_key = {k: key(k, v) for k, v in after.nodes.items()}
    b_set, a_set = set(b_key.values()), set(a_key.values())
    # Every arrow is its own fact: the third message between Client and API is not the first
    # one, so edges are keyed (from, to, ordinal) and a dropped message is a removed relationship.
    def edge_keys(edges, key):
        seen: dict[tuple[str, str], int] = {}
        out = {}
        for a, b, l in edges:
            pair = (key.get(a, a), key.get(b, b))
            seen[pair] = seen.get(pair, -1) + 1
            out[(pair[0], pair[1], seen[pair])] = l
        return out
    b_elabel = edge_keys(before.edges, b_key)
    a_elabel = edge_keys(after.edges, a_key)
    b_edges, a_edges = set(b_elabel), set(a_elabel)
    # A C4 description is a caption, judged like a label; a class field or ER attribute is a fact.
    soft = before.kind in ("c4",)
    b_members = {b_key[k]: sorted(_norm(m) for m in v) for k, v in before.members.items() if k in b_key}
    a_members = {a_key[k]: sorted(_norm(m) for m in v) for k, v in after.members.items() if k in a_key}
    b_label = {b_key[k]: v for k, v in before.nodes.items()}
    a_label = {a_key[k]: v for k, v in after.nodes.items()}

    removed_n, added_n = sorted(b_set - a_set), sorted(a_set - b_set)
    removed_e, added_e = sorted(b_edges - a_edges), sorted(a_edges - b_edges)
    common = b_set & a_set
    member_changes = {k: (b_members.get(k, []), a_members.get(k, [])) for k in common
                      if b_members.get(k, []) != a_members.get(k, []) and not soft}
    caption_changes = {k: (b_members.get(k, []), a_members.get(k, [])) for k in common
                       if b_members.get(k, []) != a_members.get(k, []) and soft}
    label_changes = {k: (b_label[k], a_label[k]) for k in common if _norm(b_label[k]) != _norm(a_label[k])}
    # Detail — a code, number, path or identifier — that left a label is ruled on over the whole
    # after-document: still in the diagram (kept), in the document's prose, a legend or a table
    # (relocated, and where), or nowhere (DESTROYED, a blocker). A %% comment is nowhere.
    diagram_text = graph_text(after)
    diagram_tokens = _tokens(diagram_text)
    context_files = [Path(x) for x in args.after] + [Path(x) for x in (args.context or [])]
    context_lines = []
    for cf in context_files:
        for ln in visible_text(cf, near_figures=cf.name in {Path(x).name for x in args.after}).splitlines():
            if ln.strip():
                context_lines.append((cf.name, ln.strip()))

    def find_in_context(token: str, old_label: str, new_label: str = ""):
        for name, ln in context_lines:
            if token_present(token, _tokens(ln), ln) and shares_context(ln, old_label, new_label):
                return (name, ln[:90])
        return None
    moved = []       # (where, token, from, old, new)
    destroyed = []   # (token, from, old, new)
    samples = []     # (token, from, old, new): example values dropped, reported, never a blocker

    def rule(old: str, new: str, origin: str) -> None:
        new_tokens = _tokens(new)
        for t in sorted(_detail_tokens(old)):
            if token_present(t, new_tokens, new) or token_present(t, diagram_tokens, diagram_text):
                continue
            hit = find_in_context(t, old, new)
            if hit:
                moved.append((hit, t, origin, old, new))
            elif t.isdigit() and PLACEHOLDER.search(new):
                # `/workorders/123` became `/workorders/{id}`: the value was generalised, not lost
                moved.append((("the after label, as a placeholder", new[:90]), t, origin, old, new))
            elif is_sample_value(t):
                samples.append((t, origin, old, new))
            else:
                destroyed.append((t, origin, old, new))

    for k, (b, a) in label_changes.items():
        rule(b, a, f"node {k!r}")
    for e in set(b_elabel) & set(a_elabel):
        if _norm(b_elabel[e]) != _norm(a_elabel[e]):
            rule(b_elabel[e], a_elabel[e], f"edge {e[0]!r} -> {e[1]!r}")
    for k, (b, a) in caption_changes.items():
        rule(" ".join(b), " ".join(a), f"caption of {k!r}")
    for k, (b, a) in member_changes.items():
        for m in set(b) - set(a):
            rule(m, " ".join(a), f"member of {k!r}")
    # A declared restructure: an entity removed from the diagram is accepted only when its label
    # and every one of its members are found, detail and all, in the document beside the figure.
    declared_ok = []
    if args.declare and removed_n:
        # The declaration is the author vouching for the move; the tool checks that every code,
        # identifier and value the entity carried is present in the document's section — a table
        # keeps the field name in its header and the value in the row, so this is a set test.
        section_tokens = set()
        for _, ln in context_lines:
            section_tokens |= _tokens(ln)
        raw_members = {b_key[k]: v for k, v in before.members.items() if k in b_key}
        section_text = "\n".join(ln for _, ln in context_lines)
        for k in removed_n:
            # the label is matched whole (plain words and detail alike), so "Refunds API | 402"
            # cannot stand in for a dropped "Billing API 402" just because the code matches;
            # a member with no detail tokens still falls back to its plain words
            label_toks = _detail_tokens(b_label[k]) | _tokens(b_label[k])
            member_toks = {t for txt in raw_members.get(k, []) for t in (_detail_tokens(txt) or _tokens(txt))}
            found = all(token_present(t, section_tokens, section_text) for t in label_toks | member_toks)
            if found:
                declared_ok.append(k)
            else:
                destroyed.append((k, f"entity {k!r}", b_label[k], "(removed; not found whole in the document)"))

    print(f"identity: {'authored ids' if by_id else 'label text (this kind has no ids)'}")
    print(f"before: {len(b_set)} entities, {len(b_edges)} relationships, {sum(len(v) for v in b_members.values())} members")
    print(f"after : {len(a_set)} entities, {len(a_edges)} relationships, {sum(len(v) for v in a_members.values())} members")
    for name, lst in (("entities removed", removed_n), ("entities added", added_n),
                      ("relationships removed", removed_e), ("relationships added", added_e)):
        print(f"{name:22s}: {lst if lst else '-'}")
    for k, (b, a) in sorted(member_changes.items()):
        print(f"members changed on {k!r}: -{sorted(set(b) - set(a))} +{sorted(set(a) - set(b))}")
    if label_changes or caption_changes:
        print(f"labels reworded       : {len(label_changes)} of {len(common)}"
              + (f"; captions reworded: {len(caption_changes)}" if caption_changes else "")
              + f"  (scope for relocated detail: {', '.join(c.name for c in context_files)})")
    for (where, ln), t, origin, old, new in moved:
        print(f"  relocated {t!r} from {origin}: now in {where}: \"{ln}\"")
    for t, origin, old, new in samples:
        print(f"  sample value {t!r} dropped from {origin}: \"{old}\" -> \"{new}\" — an example, not a fact; check it was one")
    for t, origin, old, new in destroyed:
        print(f"  DESTROYED {t!r} from {origin}: \"{old}\" -> \"{new}\" — it appears nowhere the reader can see")

    if destroyed:
        print(f"VERDICT: DESTROYED — {len(destroyed)} piece(s) of detail exist nowhere in the after-document; relocate them into the prose, an edge label or a legend the reader can see, never delete them")
        return 2
    if args.declare and removed_n and set(removed_n) <= set(declared_ok) and not [e for e in removed_e if e[0] not in declared_ok and e[1] not in declared_ok]:
        print(f"VERDICT: RESTRUCTURED (declared: {args.declare}) — {len(declared_ok)} entit{'y' if len(declared_ok) == 1 else 'ies'} moved whole into the document with every member and code accounted for: {declared_ok}")
        return 0
    if removed_n or removed_e or any(set(b) - set(a) for b, a in member_changes.values()):
        print("VERDICT: CHANGED — something the before diagram asserted is not in the after; a lost node, edge or member is a lost fact unless the merge or split is declared")
        return 1
    if added_n or added_e or member_changes:
        print("VERDICT: CHANGED — the after asserts more than the before")
        return 1
    if moved:
        print(f"VERDICT: IDENTICAL — same entities, relationships and members; {len(moved)} piece(s) of detail relocated into the document")
        return 0
    print(f"VERDICT: IDENTICAL — same entities, relationships and members{' (' + str(len(label_changes)) + ' labels reworded)' if label_changes else ''}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory(prefix="diagram-check-") as tmp:
        reports = analyse(Path(args.path), args.target, Path(tmp), args.kind)
    worst = "clean"
    for r in reports:
        d = r.width_driver
        print(f"{Path(r.path).name}#{r.index}  {r.kind}/{r.direction or '-'}  "
              f"{'nodes=' + str(r.nodes) + ' edges=' + str(r.edges) if r.parsed else 'graph=unparsed'}  "
              f"labels<=3w={'yes' if r.max_label_words <= MAX_LABEL_WORDS else 'NO'} "
              f"edges<=3w={'yes' if r.max_edge_words <= MAX_LABEL_WORDS else 'NO'} "
              f"pt@target={r.label_pt_at_target:.1f}"
              + (f"  width-driver={d['role']}:{d['words']}w" if d else ""))
        for f in r.findings:
            print(f"   [{f.severity}] {f.code}: {f.detail}")
        if r.worst == "blocker" or (r.worst == "warning" and worst != "blocker"):
            worst = r.worst
    if args.json:
        Path(args.json).write_text(json.dumps([asdict(r) for r in reports], indent=1), encoding="utf-8")
    return 2 if worst == "blocker" else (1 if worst == "warning" else 0)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="walk a tree and report on every diagram")
    a.add_argument("path")
    a.add_argument("--target", choices=sorted(TARGETS), default="md")
    a.add_argument("--json")
    a.add_argument("--kind", help="magazine target: the edition kind whose placement rules apply (the builder validates it)")
    a.add_argument("--limit", type=int, default=100000)
    a.add_argument("--verbose", action="store_true")
    a.add_argument("--exclude", action="append", help="glob or substring of paths to skip (repeatable)")
    a.add_argument("--include-fixtures", action="store_true", help="audit fixture/test-data directories too")
    a.set_defaults(func=cmd_audit)

    g = sub.add_parser("graph", help="extract nodes, edges and members for a rewrite diff")
    g.add_argument("path")
    g.set_defaults(func=cmd_graph)

    d = sub.add_parser("diff", help="compare a before diagram with one or more after diagrams")
    d.add_argument("before")
    d.add_argument("after", nargs="+")
    d.add_argument("--context", action="append", help="a document, legend or prose file that carries relocated detail (repeatable); an after .md is its own context")
    d.add_argument("--declare", help="declare a restructure: entities removed from the diagram are accepted only if found whole, members and codes included, in the document")
    d.set_defaults(func=cmd_diff)

    c = sub.add_parser("check", help="gate one diagram")
    c.add_argument("path")
    c.add_argument("--target", choices=sorted(TARGETS), default="md")
    c.add_argument("--json")
    c.add_argument("--kind", help="magazine target: the edition kind whose placement rules apply (the builder validates it)")
    c.set_defaults(func=cmd_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
