---
name: diagram
description: Add, fix and improve diagrams in documents - choosing the right diagram type rather than defaulting to a flowchart, keeping labels short so they stay legible, and redrawing without losing what the diagram asserts. Works over one document or a whole tree. Use when he says "diagram", "diagrams", "make a diagram", "fix these diagrams", "add diagrams", "the diagrams look bad", or points at a document that needs figures.
---

# Diagrams

Edward has hundreds of diagrams across his documentation and most of them have problems. He can
already tell a bad diagram by looking; what costs him is the manual work of fixing them, and
deciding where a document needs one it has not got. **This skill does the work, not the critique.**

A baseline audit of a real documentation tree at the ADO target, fixtures excluded, is what
`scripts/audit.py audit` prints; re-run it rather than quoting a stale figure. (A once-quoted
"22-word label" in this file came from a `fixtures/label-length-fail-very-long.mmd`-style file, a
diagram written to fail the validator; fixtures are skipped by default now.) The shape it shows:
most diagrams are illegible at target width, most of those because of label length, a good share
have too many nodes for one figure, and a minority are flowcharts drawn around what is really a
graph.

**The first two are the same problem.** Long labels make wide nodes, wide nodes make a wide
diagram, a wide diagram is scaled down to fit, and the text becomes unreadable. Fix the labels and
legibility follows — **the labels that drive the width**, which differ by type: a flowchart's node
labels, a sequence diagram's message text, a class diagram's members, a gantt's task names, a C4
element's description. The audit names the width driver; aim there. Never respond to small type by
changing the font or the margins.

## The engine

`scripts/audit.py` does the measuring. It is the gate, not a report:

```bash
python ~/.claude/skills/diagram/scripts/audit.py audit <path> --target ado --json out.json
python ~/.claude/skills/diagram/scripts/audit.py check <file> --target magazine   # exit 2 = blocker
python ~/.claude/skills/diagram/scripts/audit.py graph <file>                     # nodes, edges, members
python ~/.claude/skills/diagram/scripts/audit.py diff <before> <after> [<after2>…] # the redraw gate
```

**Before trusting a change to `audit.py`, run its own suite** — one case per check, each with a
fixture that fails without the fix it guards:

```bash
python ~/.claude/skills/diagram/tests/selftest.py     # prints N/N; every case must pass, or it is not safe to use
```

It has been mutation-tested: dropping one word boundary from the flowchart keyword guard turns a
passing case red. A gate suite that cannot go red is decoration, so keep that property — every new
check arrives with a case that fails without it, and the count in the tool's own output is the
one to trust, never a number quoted here.

It renders every diagram and measures from the rendered SVG, where every piece of text is present
with its real size: **the smallest label at the target's real width**, the widest text run and its
role (node, edge or message, member, note), the height at target width, text that overflows a
fixed box or has a lifeline struck through it, node and edge label word counts, node and edge
counts, back-edges by rank and multi-parent nodes, the diagram type, and target-specific breakage
(every digit-only hex named, `%%{init}%%` directives, an unterminated directive). `graph` extracts
what a diagram asserts; `diff` compares a before with one or more afters (a split is several
afters) and rules IDENTICAL, CHANGED with the lists, or **UNVERIFIABLE** when either side is a
kind the tool cannot parse.

**The gate fails closed.** A diagram that renders but whose text the tool cannot place — no
width to scale from, or no run it can call a node, edge or member label — is `unmeasured`, a
blocker, not a pass. Quiet is the worst failure mode; a check that cannot fail is no check.

**Target widths are a choice, not a measurement.** 6.5in is the floor Edward set as the strictest
realistic surface — a wiki column, a printed page inside its margins, a narrow window — and a
diagram legible there is legible everywhere. Widening it is closed as a question; a diagram under
the floor at 6.5in needs authoring, not a wider ruler.

**The magazine target measures what prints.** A wiki scrolls, so there a figure is fit to the
width only; a printed page does not, and the magazine shrinks a tall figure to the page height.
`--target magazine` asks the builder itself where it would place the figure (`--place`) and
measures at that scale, so the gate and the edition report one label size; pass `--kind` when the
edition's kind is known, as the publish board does.

**The real constraint is said first.** Six sequence participants are six 150px boxes and five
50px gaps before a single message is written, and at 6.5in that is already under the floor: the
audit says `needs-author` with the participant count up front, so nobody spends a round shortening
messages that were never the problem. The same for a diagram over the node budget that is
illegible: split first, labels second. A figure over three pages tall is a blocker; over a page
and a half is a warning.

**What a reader sees in the first two seconds is measured, with the cure named.** Mermaid draws
a lifeline straight through any message text that sits on it: a self-message (`A->>A`) at any
length, and a message that spans a third participant, whose text is centred on that
participant's line. Both are structural — no label length changes them — so both are warnings
that name the way out: a `Note right of` beside a self-loop; for spanning messages, put the
participants that talk side by side, or `sequence.messageAlign: left` where the surface allows a
directive. Text wider than its own gap is a blocker where it can happen. Overflow — text leaving
a box — is claimed only where a box can be fixed (Graphviz `fixedsize`, explicit widths); mermaid
sizes every box it draws to its text, so the tool does not cry overflow there.

**Splitting a sequence diagram** (the cure for six or more participants) is a mechanical
discipline: every message and note copied by exact text and placed exactly once, the boundary a
stage or the hop between two API surfaces, participants declared per figure, a message over
about eighteen characters re-broken with `<br/>` (a space to the gate), a path or identifier
moved to a note spanning the same two participants, a long identifier broken at its camel-case
seams, and the union verified IDENTICAL by `diff`. Five participants is the ceiling at 6.5in —
they alone are 7.1pt — and a nested `alt` costs the rest, so four is the number to aim for.

**What the tool reads and what it only measures.** It extracts entities from flowchart, Graphviz,
sequence, state, gantt, class, ER, C4, mindmap and pie sources (a pie's slices are its entities,
their values its members), with quoted text masked so a parenthesis inside a label never becomes a
phantom node. For any other kind (journey, timeline, quadrant, sankey, block, requirement, git
graph) it renders, measures legibility and label length
from the SVG, and reports `unparsed`: no node count, no size or type-fit verdict, and `diff`
abstains. An IDENTICAL from `diff` is a verified claim; an UNVERIFIABLE is an instruction to
compare by eye and say so in the report.

**Identity in the diff is the authored id** (flowchart, state, class, ER, C4, sequence alias,
Graphviz, gantt task id), and every arrow is its own fact: the third message between two
participants is keyed apart from the first, so a dropped message is a removed relationship, never
absorbed. A node written `A[Alpha] --> B[Beta]` is read the way people write it; keywords such as
`end` and `subgraph` are matched whole, so a node named `endpoint` is a node. Labels may be
reworded — that is what fixing legibility is — and the diff lists the rewordings. A mindmap has no
ids: its text is its identity, and shortening a leaf is a change of assertion, reported as one.

**The document is the unit of fidelity, not the diagram.** Every piece of detail that leaves a
label — a code, a number, a path, a slash-joined term like `HTTP/HTTPS`, an acronym, an identifier
— is ruled on over the whole after-document: still in the diagram, **kept**; in the prose, a
legend or a table the reader can see, **relocated**, and the diff says where; nowhere,
**DESTROYED — exit 2, the redraw is refused.** An after `.md` is its own scope, narrowed to the
figure's section and the sixty lines beneath the fence; a `.mmd` that lives in a wiki page needs
that page (or the legend) passed with `--context`. A line counts only if it shares a word with
the old or the new label, or two of the old label's codes, or is a bare value on a line of its own
(a response example) — a `204` in "throughput peaked at 204 requests" on the far side of a
document is not a relocation. Notes and the rendered title are diagram scope; a `%%` comment is
nowhere. The matching is not whole-string: `/workorders/` is present in
`/api/v2/workorders/{id}`, a `123` that became `{id}` was generalised, not lost; `InternalAPI`
written as `Internal API` is kept; `Installer_ID` is kept by `woDetail.Installer_ID` and the
reverse — a local variable's prefix is not part of the name — but a type or namespace prefix is
(`Console.WriteLine` is not kept by `WriteLine`), and so is any prefix whose member says nothing
alone (`order.Id` is not kept by `Id`); the rule lives once, in `scripts/presence.py`, shared with
the edit gate; a token cut by an ellipsis is a prefix; `e.g.` is prose; and a bare number of four or
more digits is an example value, reported as dropped but never a blocker. A gate that cries wolf
is a gate that gets ignored, which is worse than none.
An entity moved whole into a table beside the figure is a **declared restructure**: pass
`--declare "<reason>"` and the diff accepts the removal only when the entity's label and every
member, code and identifier are found in the document, else DESTROYED. Exit codes: 0 identical,
reworded, relocated or declared; 1 changed (a lost or added node, edge or member with no
declaration); 2 destroyed; 3 unverifiable.

## Rules that are not negotiable

**Labels: three words maximum, one where it will carry the meaning — node labels and edge or
message labels alike.** Detail goes into the prose, or a legend. A sentence in a box is a
paragraph that lost its way; a sentence on an arrow is worse. Notes and titles are prose by design
and are exempt from the three words, but a note over twenty words is a paragraph and the audit
warns (`long-note`): it belongs in the document.

**A redraw may change type, direction, engine and styling. It may not change what the diagram
asserts.** Run `diff` before and after: same entities, same relationships, same members. A lost
node is a lost fact; so is a status code that lived in a label and now lives in a `%%` comment the
reader never sees. When an entity genuinely leaves the diagram for a table or the prose, that is a
declared restructure — `diff --declare "<reason>"`, which passes only when the entity is found
whole in the document — never a quiet edit and never a sentence in a report standing in for the
gate. For a kind the tool cannot parse, say that the gate could not check.

**Judge rendered, never from source.** A diagram that reads fine on a monitor prints at a third of
the size. Every diagram defect worth finding was invisible in the markup.

**Author to the strictest target.** Hex colours containing a letter — all of them, the audit lists
every offender — and styling in `classDef` rather than a directive. Those cost nothing on GitHub or
in print and are the difference between working and corrupted in an Azure DevOps wiki. One source,
every surface.

## Choosing the type — the highest-value decision

Machine-made diagrams default to flowcharts because a flowchart never refuses input. It is the
commonest defect in the corpus and the easiest to fix.

| The relationship the content holds | The right shape |
| --- | --- |
| Interactions between actors, ordered in time | sequence |
| A thing with states and transitions between them | state |
| **Arbitrary connection — dependencies, call graphs, topology, lineage** | **a graph, in Graphviz** |
| A procedure with decisions and one path through | flowchart, legitimately |
| Containment or hierarchy | tree, or subgraphs |
| A data model | ER |
| A comparison across attributes | not a diagram — a table |

**The tell for a mis-drawn graph:** back-edges, and nodes with several inbound edges. `audit.py`
reports both, with back-edges judged by rank so that a decision tree whose branches converge on a
shared error node is not mistaken for a graph. A flowchart with real back-edges and several
multi-parent nodes is a graph that was drawn wrong, and Graphviz (`dot`, `neato`, `fdp`, `sfdp`)
lays it out far better than forcing it into a top-down flow.

**Language follows the type and the target.** Mermaid for sequence, state, ER and true flows, and
anywhere the source must stay live markup in a wiki. Graphviz for genuine graphs, rendered to SVG
and embedded as an image; idiomatic `//` comments are fine, the tool strips them before sniffing the
type. Escalating to Graphviz is a decision the measurement makes: when a diagram cannot meet the
legibility floor as Mermaid at its target width, that is the trigger.

**Graphviz is installed on this machine** (`winget install Graphviz.Graphviz`, 2026-09), at
`C:\Program Files\Graphviz\bin\dot.exe`. It is **not on PATH** in the shells Claude Code opens, so
`which dot` says no and has misled a session before: `audit.py` and the magazine builder both fall
back to that path on their own, and a shell that calls `dot` directly needs
`export PATH="/c/Program Files/Graphviz/bin:$PATH"` first. Search before saying it is missing.

## Working one document

1. **Audit first.** Every existing diagram, at the document's target. Read the width driver.
2. **Fix in cause order** — the labels that drive the width, then type, then size, then direction,
   then styling. Most legibility problems are solved by the first step alone; when the driver is a
   member list or a message, shortening node labels changes nothing and the audit will say so.
3. **Re-audit after each change, and `diff` the graph.** Measured, not assumed. A diagram whose
   pt did not move after a label edit was edited in the wrong place.
4. **Then look for gaps**: passages whose concept the reader is holding in their head — a sequence
   of actors, a set of states, a structure described through nested prose. Be restrained: **at most
   one new figure per section** unless the section is a walkthrough, and only where the relationship
   is genuinely hard to hold in prose.
5. **Minor prose edits are allowed** to introduce a figure and refer back to it. A figure nobody
   introduces is an orphan and counts as a defect. Do not rewrite beyond those sentences.
6. **Report** what changed, what was left alone and why, any diagram that could not be made
   legible at its target with the reason, and any diff that was UNVERIFIABLE.

## Working a tree

For a corpus, this is a queue, not an artisan job:

1. `audit --json` the whole tree and rank by reading cost — blockers first, worst label size first.
   Fixture and test-data directories are skipped by default and the count is printed;
   `--include-fixtures` audits them, `--exclude` skips more.
2. Report the shape of the problem before fixing anything, so the scale is visible.
3. Fix in ranked order, re-auditing as you go, and **checkpoint progress to disk** so stopping
   costs only what is in flight.
4. Keep a before/after render for each, and say what the numbers were and are.

Stop when asked. Report the queue position.

## Restraint

- **Leave good diagrams alone.** Churn carries risk and gains nothing. Name them as deliberately
  kept rather than silently skipping them.
- **Do not add a figure to every section.** A document peppered with unnecessary diagrams is worse
  than one with none.
- **Do not convert a type on a hunch.** The back-edge and multi-parent evidence is what justifies
  calling a flowchart a graph; without it, leave it.
- **Do not trim a label into nonsense.** "Internal detail hidden on 500s" to "Hidden on 500s" meets
  the word rule and loses the thought. Three words that carry the meaning, or a legend.
- **A 37-node diagram is split, not trimmed.** Shorter labels on an oversized diagram buy a point
  or two and leave it unreadable; the audit's `oversized` finding is the instruction.
- When a diagram cannot be made legible at its target in any orientation, it needs authoring —
  fewer participants per figure, a split by a boundary a reader would recognise, every entity,
  message and note landing exactly once and the union verified by `diff`. "Unfixable at this
  width" is not a finding; the width is fixed and the diagram is the variable.

## Roles

Two jobs, whether or not a persona system is installed to carry them:

- **The author.** Type selection, the label rule, splitting, target discipline, preserving what a
  redraw inherits — the rules earlier in this file.
- **The reviewer.** Renders and measures, rules on type fit and legibility, traces a symptom to its
  cause, finds the passages that need a figure — what `scripts/audit.py` does, read through this
  file's judgement calls.

Review first to build the queue, then author through it. If a persona system such as Personetta is
installed with dedicated diagram recipes, its `design-diagram` and `review-diagram` roles can carry
these two jobs; without one, follow this file directly — nothing here depends on it being present.

## Repo conventions

If the repo states a diagram contract, it wins. A `process-docs/diagram-authoring.md`-style file is
the fullest kind of example: one diagram per file, raw source with no markdown fence, required
frontmatter, `%%` comments only, and the ADO-safe colour rule (**every hex literal must contain a
letter** — Azure DevOps substitutes `#<digits>` as a work-item mention inside mermaid and corrupts
the diagram). A repo with its own `validate-diagrams.py` and an embed pipeline that strips
directives on the way to the wiki should have that pipeline called rather than duplicated. Its
`**/fixtures` directories hold diagrams built to fail that validator; they are not part of any
corpus statistic.
