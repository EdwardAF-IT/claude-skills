---
name: magazine
description: Turn markdown documents he already has into a colorful, printable magazine-style edition for reading away from the screen - masthead, columns, 10pt serif body, real page layouts, diagrams as figures. Use when he says "magazine", "printable", "make this printable", "reading copy", "something I can print", "read in the comfy chair", "read on the plane", or asks for desktop-publishing-style output.
---

# Magazine edition

Edward reads long documents away from the keyboard, and he asks for this more and more often, across
projects.

**The layout is not decoration — it is what gets the document read.** In his words: *"I'm more
likely to read a dense technical doc if it's pleasant to read and easy to follow."* So the measure
of a good edition is whether someone can follow the argument on paper, not whether it looks busy.
Take it seriously as craft: *"not many people appreciate the art of publishing much anymore, but I
do. My original hyperobsession was desktop publishing on an Amiga in the 80s."*

He likes **columns** — reach for them whenever the prose is long-form enough to carry them.

## The two rules that never bend

From the original ask, verbatim: *"don't overwrite the originals — add new files. And don't change
any wording — I want to read the exact words that are on the disk right now."*

1. **Only ever add files.** The source markdown is a read-only input.
2. **Not one word changes.** Same prose, same order, same tables. Pull the text programmatically from
   the file rather than retyping it, so fidelity holds by construction. If the writing needs work,
   that is a different request.

Diagrams are the one exception — *"even add charts or diagrams if helpful"* — so a figure that makes
a mechanism legible is welcome. Prose is still untouched.

**The builder proves the second rule on every build.** After rendering, it strips the tags from the
edition and looks for every non-blank source line (and every table cell) in the result; one missing
line fails the build with the line number. A recogniser that loses a nested bullet is a defect,
not a trade-off — that exact bug has happened, which is why the check exists. Never pass
`--no-verify` on an edition that ships.

## What he asked for, concretely

*"a readable 10-pt font for the body text, good page layouts, color, whitespace, even add charts or
diagrams if helpful."*

- **Body 10pt**, on a 13.5pt baseline unit, with a real type scale for headings and a masthead
  carrying title and date. A contents block once there are six or more sections, or more than one
  document.
- **Serif or sans depends on the document kind** (below). Long-form reading matter is serif;
  his planning and assessment documents in `truing` and `career` are sans with serif reserved for
  the masthead. Either way it is one deliberate choice, declared once as a `:root` variable.
- **Layout follows the content.** Long prose reads in two columns; a memo reads in one; a work
  breakdown, an assessment or a comparison reads as a single column of cards, pills and tables —
  which is what his existing printables do. The builder decides this once per edition.
- **Colour carries structure**: section numerals, the rule over an h3, pull-quote rules, the
  verdict label, contents numerals, the drop cap. Status hues appear only through pills and
  diagrams, one meaning each for the whole edition. Never decoration at random.
- **Pull-quotes** lifted verbatim from the prose, never written for the occasion, and placed a
  block away from the sentence they repeat.
- **Diagrams rendered as figures** at build time, sized so their labels print at 8pt where a
  placement allows and never below 7pt without a warning naming the figure. A diagram that prints
  as a code fence is a defect; so is one whose labels cannot be read.
- A folio (title and page number) at the foot of every page but the first.

## The two defects he has already had to report — check both

- **Whitespace holes.** *"The magazine looks great except for one thing… there are several pages that
  have a lot of white space."* Widows, orphans, a figure forced to the next page leaving a half-empty
  one. Tune the break rules and re-render; do not ship a document with gaping pages. The one hole
  the builder cannot close is the page before a full-page plate when the source puts only a few
  paragraphs between a section start and the plate: say so when handing over, rather than hiding it.
- **Print not matching the screen.** *"The printout of the proposal looks different than the html.
  How can we have it look just the same?"* Whatever you previewed must be what prints — same
  stylesheet, same paginated path, no screen-only CSS doing work the print path does not honor.

**Look at the rendered output before handing it over.** He asked for this explicitly: *"make sure to
review them."* Print it to PDF through Chrome and look at every page. Measure rather than trust: the
body is 10pt, plate labels are at or above 7pt (the build prints each figure's size), no page is
mostly white, no heading is orphaned at a page foot.

## How to build it — use the bundled builder

This skill ships its own tooling. Prefer it over hand-writing HTML:

```bash
node ~/.claude/skills/magazine/scripts/build-magazine.mjs \
  --out docs/design/coordinator-loop-print.html \
  --kicker "Design" --subtitle "..." \
  docs/design/coordinator-loop.md
```

- `scripts/build-magazine.mjs` — markdown to one self-contained HTML file. Node's standard
  library plus `mmdc` for diagrams. Handles headings, paragraphs, nested lists of any depth, task
  lists, pipe tables, fenced code, blockquotes, rules, images, links and inline formatting. Source
  files are read-only; prose is converted, never rewritten, and the fidelity check proves it.
- `assets/magazine.css` — the palette, type scale, spacing unit, masthead, columns, every
  component and the print block. Inlined into every edition.
- `assets/mermaid-theme.json` — the mermaid configuration: the same named colours as the
  stylesheet, 16px labels, tight node and rank spacing so plates print larger.
- **Code blocks are syntax-coloured** by a global highlight.js (`npm i -g highlight.js`, installed
  on this machine) at build time; without it they print plain. A fence names its language or
  stays plain. The palette is print-tuned: keywords and member names bold, strings the accent,
  comments soft italic — weight carries it, so a mono laser loses nothing.
- **Diagrams need `mmdc` on PATH** (`npm i -g @mermaid-js/mermaid-cli`, installed on this machine).
  Without it a document with a mermaid fence fails to build; `--mermaid cdn` is a screen-only
  preview that needs a connection, never a deliverable.
- **A `dot` or `graphviz` fence is a plate too**, drawn by Graphviz — the diagram skill's
  escalation for a real graph. `dot` is installed at `C:\Program Files\Graphviz\bin` and the
  builder falls back to that path when it is not on PATH (it usually is not, in Claude's shells).
  Its labels are measured from the SVG's own `font-size`, and it flips `rankdir` the way a
  flowchart is flipped.

### Flags

`--kind feature|brief|dashboard` overrides the inferred document kind. `--columns` / `--single`,
`--serif-body` / `--sans-body` and `--landscape` override what the kind decided. `--kicker`,
`--subtitle`, `--thesis`, `--title` fill the masthead. `--toc` / `--no-toc` force the contents block.
`--accent "#rrggbb"` recolours the accent. `--diagram-direction keep` stops the LR-to-TD transposition
of wide flowcharts. `--css <path>` overrides the stylesheet. Several input files combine into one
edition with a contents block per document.

### The document kind — decided once per build

The builder reads the whole edition's shape and picks one of three kinds; the build output says
which, and why (words, sections, figures, widest table). Everything below the recognisers — type
scale, spacing unit, palette, print block — is shared. The kind sets the rest:

| Kind | When | Columns | Body | Masthead | Contents | Active shapes |
| --- | --- | --- | --- | --- | --- | --- |
| **feature** | 2,000+ words of prose | two, 3.65in, 56-64 characters | Georgia 10/13.5; tables 9.5/13; code 7.5/10.5 | 30pt, kicker, 4px rule | at 6+ sections | everything below, plus decks, drop caps and pull-quotes |
| **brief** | under 2,000 words | one, 34em | Segoe 10/14; code 8/11 | 22pt, 2px rule, no kicker | never | cards, ladders, run-ins, verdicts, decks |
| **dashboard** | a table of 8+ columns (landscape), or tables and code outweighing prose | one for exhibits; a prose run of 120+ words between them flows in two | Segoe 10/14; tables 10/13.5 (9.5 at 8+ columns) | 22pt, 2px rule | at 6+ sections | cards, ladders, run-ins, verdicts, status pills |

A brief under 1,500 words whose plate would need a landscape sheet becomes a landscape edition
altogether: one page size, the plate in the flow, no sheet to turn.

A document dense with the author's own quotations (one blockquote per 400 words, or quotations over
a fifth of the text) gets quiet quotes — an indented hairline, no tint — and no pull-quotes.

### What the builder recognises

It does not just style markdown; it reads the shapes markdown already carries and gives each one
its own form, because a page where every kind of information looks the same reads as a wall:

| Markdown | Becomes |
| --- | --- |
| Table whose cells are prose | Record cards two to a row (a row moves whole; neither a grid nor a multicol fragments predictably in Chrome), the table's header row kept once above them; records over 160 words are stacked full-width so they can break |
| Two-column term/meaning table | Definition list at body size, the header words kept above it |
| Column with a handful of repeated status words | Status pills, hue from a fixed lexicon (green = exists/passed/yes, amber = later/pending, red = blocked/failed/no, blue = new), text unchanged |
| List whose items open in bold | Card grid (8 or fewer, short bodies), or a run-in list; the separator after the bold (`:` or a spaced dash) stays with its label |
| Any list whose items run to paragraphs (over 120 words each) | Text, for the focal rule: emitted in pieces so a pull-quote can sit between items, the numbering intact; long items may break across a column |
| List whose items share the same sub-leads ("Was:/Is:", "Today:/Under…:") | A ladder of rungs with fields; two fields print side by side in a single column |
| Three or more bold-lead paragraphs, each optionally followed by its own list — or two, when both leads are five words or fewer | A ladder; the list becomes the rung's fields when every item has a lead; numbered when the leads are ("Step 0" shows 0); a rung over 120 words (60 with fields) may break between its parts |
| A lone bold-lead paragraph | The lead in sans, no rule, no ground — one paragraph, not a rung |
| "Recommendation:" (or Verdict, Answer), "Decided:", "**Pending.**" inside a list item or rung | A fielded rung: the question in ink, the recommendation under an accent rule on a faint neutral ground, the decision on the verdict's blue ground, a pending one on none — the whole item framed as a card with a hairline border, accent rule and its number set large, so one ask never runs into the next (a Verdict alone is a step's outcome and gets no card). One answer lead is enough to field a list; a decision counts on a single item |
| `### Q1.` heading | A band across the column — tint ground, accent rule at the left, the author's number set large in accent — so a new question is seen before it is read; the decision block's blue closes it |
| `####` heading over one paragraph of 80 words or fewer | A run-in sub-head on the paragraph's first line |
| Paragraph opening "Recommendation:", "Verdict:", "Decision:" | Verdict panel |
| Numbered `##` heading | Numeral (with its own punctuation), 20pt display heading on white |
| First paragraph after an opener, 15-70 words, ending in a full stop | Deck — never a colon-ended lead-in |
| First long paragraph after an opener (feature) | A three-line drop cap on the author's own initial |
| Blockquote before the first section | Colophon, set small |
| Short paragraph introducing a mermaid fence | The plate's caption, in its own place, inside the plate's frame |
| 320 words of body text with no other entry point, in a section of 300+ (feature) | The next emphasised phrase of six words or more lifted verbatim, left in place, and set one block later in a single column at 16/20; again after every further 320 words |
| Mermaid fence | A plate sized at build, the first placement whose labels reach 8pt (failing that, 7pt): in a column; in the flow at up to 60% of a page; a tall column plate with prose beside it (in a single column, a local two-column section carries the text that follows); a strip three times wider than tall is turned on its side as a column plate; a portrait plate; a landscape sheet, only for a plate at least 40% of that sheet tall, with the text that follows filling the rest of the sheet. When the author's direction falls short the other direction is rendered too and kept if it prints labels 15% larger. Labels are capped at 10pt (`--label-cap`): a plate is never enlarged past body size because the page has room, which is what starved the text under it |
| Sequence diagram | Each participant one hue, held across the edition by its printed label (blue, green, violet, teal, amber, orange); a new name takes a hue no other actor on its plate has, least-used in the edition first, grey only past six on one plate; lifelines, arrows and message text stay ink |
| Table body | Every second row on the neutral ground; the foot rule in ink-soft; the head row keeps the table's one colour |
| Card grid | Cards on the neutral ground with an ink-soft rule at the head — the record card's rule turned ninety degrees; no wire border |

An art director's pass of 2026-09-20 is the reasoning behind the last six rows, and names what was rejected: coloured card titles, a hue per card set,
coloured code spans, a second accent, first-line indents, sidebars with written text.

**The wording is never touched** — every one of those re-containers text. Bold-lead separators,
heading numerals' punctuation, field colons, definition-list and record-card headers all stay,
because the fidelity check would fail otherwise. HTML comments are the one thing dropped: they are
markup. The check compares raw source text against the edition's text decoded once, so a literal
`&lt;` in the source (a 59,000-word readme found this) is not a false alarm.

**What the corpus taught.** Seventeen documents from nine repos — a one-paragraph persona spec, a
changelog, a runbook, a CLI reference, an ADR, a 10-column balance table, a Q&A transcript, a
diagram page, a 59,000-word design readme — all build clean with the kind inferred. What a general
skill will not make beautiful: a document that is one enormous flat list (the readme prints as 88
pages of labelled paragraphs with a pull-quote every page or two, which is what its source is), and
a single-column document whose plate needs a whole page (the page before it ends where the text
ends, because nothing may be reordered to fill it). Both are reported, never hidden.

**Accent discipline matters more than it sounds.** Colour must mean something: the accent marks
section numerals, the rule above an h3, pull-quote rules, the verdict label, the drop cap. When it
painted every card, badge and table head instead, a count on one edition went from 96 accent-painted
elements to 178, and it stopped signalling anything at all.

**Plates.** The build prints each figure's placement, printed size and label size. A label below
7pt is a warning naming the figure: the diagram needs fewer ranks or shorter labels, and that is the
author's call, not the builder's. Tell him which figures fell short.

Extend the builder when a document needs something it does not yet do — it is ours to improve. What
it does not do is edit the source markdown.

After building, **print it and look at it**, then apply the review checklist above.

### If you hand-write one instead

The pattern to match, and what the bundled CSS implements: **a single `.html` file with everything
inlined, which he opens and prints from the browser.** Working examples:

- `C:\Code\truing\planning\work-breakdown-print.html`
- `C:\Code\truing\planning\system-name-clearance.print.html`
- `C:\Code\career\Job Search 2026\Positioning Assessment (Printable).html`

The shape those share, and that a new one should keep:

- **Everything inline** — the whole stylesheet in one `<style>` in `<head>`, diagrams as inline SVG.
  One file he can move, mail or archive.
- **A named palette on `:root`** — `--ink`, `--ink-soft`, `--paper`, `--line`, plus semantic pairs
  each with a tint (`--blue`/`--blue-bg`, `--green`/`--green-bg`, `--amber`, `--red`, `--violet`).
  Colour is assigned meaning, then used consistently.
- **A font trio as variables** — `--serif: Georgia, "Palatino Linotype", serif`, `--sans: "Segoe UI",
  "Trebuchet MS", Arial`, `--mono: Consolas, Menlo, monospace`.
- **One spacing unit** — the body leading — and every vertical space a multiple of it.
- **A `.page` wrapper that looks like a sheet** on screen, which the print rules then flatten.
- **A masthead**: uppercase letterspaced kicker, `h1`, subhead; a rule under it that is a rule, not
  a bar.

### The print block that makes the printout match the screen

This is the fix for *"the printout looks different than the html"* — browsers drop background colour
when printing unless told not to:

```css
@media print {
  html, body { background: #fff; }
  body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .page { box-shadow: none; margin: 0; max-width: none; border-radius: 0; }
  h2 { break-after: avoid; }
  .pagebreak { break-before: page; }
  @page { size: letter; margin: 0.58in 0.5in 0.55in; }
}
```

Set `@page size` to match the content — his landscape work-breakdown uses `11in 8.5in` with
`margin:0` and the padding inside `.page`; a portrait document uses `letter` with a real margin.
Frames may break, atoms may not: `break-inside: avoid` on cards, rungs, figures and table rows, and
`break-after: avoid` on headings, is what prevents the whitespace holes.

**Naming:** he uses `<name> (Printable).html`, `<name>-print.html` and `<name>.print.html`. Match
whatever the folder already does; when starting fresh, `<name>-print.html` beside the source.

### When a PDF is the deliverable

Some of these end up as `.pdf` — the career résumés and cover letters, maestro's research digest.
Produce the HTML first, then print it; never hand-build a PDF. Headless Chrome prints a served page
faithfully (`file://` is blocked for the mermaid path, so serve the folder); the browser's own
"Save as PDF" is the same engine.

**In maestro only**, a sanctioned pipeline already exists and must be reused rather than duplicated:
`docs/research/magazine/magazine.css` for the columned digest layout, `mmdc` for inline SVG, and
`node docs/guide/pdf-pipeline/render-guide-pdf.js <assembled.html> <out.pdf>` — the repo's only
renderer. `build-digest.mjs` beside that stylesheet is a bespoke one-off for the research corpus
(its own header says a general pipeline was out of scope): read it for the assembly pattern, don't
feed other documents through it.

Elsewhere, hand him the HTML and let the browser's own "Save as PDF" do it, unless he asks for a PDF
on disk — then ask before adding any toolchain to that repo.

## Steps

1. Confirm which documents, and whether they become one edition or several. A batch of design docs
   is usually one edition each; a themed set reads better combined. If the ask makes it obvious,
   don't ask.
2. Build. Read the kind line and the figure lines the build prints; if the kind is wrong for the
   material, force it with `--kind` rather than fighting the flags one by one.
3. Print it and look at every page against the defect list above. Fix and re-render rather than
   shipping it. Report any figure the build warned about.
4. Write the result next to its source, lowercase filename, never a session temp folder.
5. Report the paths, one line each, and the kind the builder chose.

A large batch can go to parallel agents — separate output paths, and every one still gets step 3.

## Which model this needs

**The building is mechanical; the looking is not.** Document-kind inference, the recognisers, plate
placement, the type scale and the fidelity gate all live in `build-magazine.mjs` and
`magazine.css`, and they fail the build rather than degrading quietly. Steps 1, 2, 4 and 5 run fine
on any model, including a cheap one — those floors are guaranteed by code, not by judgement.

**Step 3 is the exception.** Whether a page actually reads well — a cramped table, an orphaned
heading, a diagram technically above the label floor and still unreadable, a section whose rhythm
went flat — is taste. A weaker model tends to see `exit 0` and call it finished. Every substantive
defect in this skill's history was found by looking at pages, not by reading build output.

So:

- **A quick build for himself** — any model. Run it, glance at it, done.
- **A document he will sit down and read**, or any change to the builder or the stylesheet — do
  step 3 properly. If the session is on a cheaper model, **dispatch the examination to a stronger
  one** rather than switching his session: an agent on Fable, handed the built PDF and the defect
  list, told to measure rather than trust and to keep fixing until it would sign off. Same move
  [[design]] makes, pointed at review instead of throughput.
- **Say which you did.** "Built, not examined" is an honest report and lets him decide. Silently
  skipping the look is how a bad edition ships.

Never call an edition reviewed on the strength of a clean exit code. The gate proves no words were
lost. It proves nothing about whether the result is pleasant to read, which is the whole point.

Pairs with [[design]], which offers a reading copy once a proposal lands.
