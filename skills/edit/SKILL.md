---
name: edit
description: Tighten the writing in a markdown document or tree without losing a fact - measure where a reader pays most, rewrite in ranked order, and refuse any rewrite the fidelity gate catches dropping content. Use when he says "edit", "tighten", "too wordy", "too dense", "hard to read", "make this readable", "copyedit", or asks for better written documentation without cutting the substance.
---

# Edit

Edward reads long technical documents, and reads more of them when they are pleasant. After the
diagram and magazine skills fixed the figures and the pages, the words were still the tax: *"it's
just too wordy and dense, not that I want to shortchange the information. I'm a smart person and
can get through it, but it's much more work than it has to be. I want better written
documentation without sacrificing any of the essential content."*

**This skill does for prose what the diagram skill does for figures: measure, fix in ranked order,
and gate.** The content is the invariant. Every rewrite is judged by two questions, in this order:
did any fact leave, and does it read more easily. A rewrite that fails the first is refused
whatever it does for the second.

## The engine

`scripts/prose_audit.py` measures and gates. It is the gate, not a report:

```bash
python ~/.claude/skills/edit/scripts/prose_audit.py audit <path> --json out.json   # the queue
python ~/.claude/skills/edit/scripts/prose_audit.py check <file>                  # one document, in order
python ~/.claude/skills/edit/scripts/prose_audit.py diff <before> <after>          # the gate: exit 2 = refused
```

**Before trusting a change to it, run its own suite** — one case per check, each with a fixture
that fails without the check it guards:

```bash
python ~/.claude/skills/edit/tests/selftest.py     # 26/26, or it is not safe to use
```

A gate suite that cannot go red is decoration; every new check arrives with a case.

### What it measures

Per section (h2/h3), the numbers an editor takes by hand: words per sentence and the share of
sentences over 30 words; words per paragraph; **walls** — 300+ words of body text with no
heading, list, table, figure or quote to land on; code spans per hundred words; parentheticals
and dashes per sentence; the passive share; nominalisations (`-tion`, `-ment`, `-ness`) per
hundred words; filler phrases ("in order to", "note that", "the fact that"); and a reading
grade. One **cost** number ranks them, weighted toward what makes him re-read: long sentences,
walls, nesting. It is a rank, not a score of quality — the queue, in the order to work it.

`check` names each wall by its start line and the three longest sentences by line, so the author
opens the file at the right place.

### The fidelity gate

`diff before after` extracts every piece of content that carries a fact by its exact form —
code spans, identifiers (CamelCase, snake_case, dotted paths, file paths, CLI flags, acronyms,
`T-153`/`P-01`/`Q12` ids, `§7.3` references), numbers with their units, link targets, headings,
table cells, and every fenced block byte for byte — and looks for each in the after.

- **Kept** (exit 0): every fact present. Relocation is allowed: a fact may move to another
  paragraph, a list, a table. `InternalAPI` written as `internal API` is kept; `30 s` and `30s`
  are the same fact; a `1337` that vanished is an example value, reported but never a blocker.
- **Changed** (exit 1): a heading or table cell reworded or gone. Allowed with
  `--declare "<reason>"`, never silently.
- **DESTROYED** (exit 2): a fact is nowhere in the after. The edit is refused. Put it back, or
  move it to prose, a legend or a table — a declaration does not excuse it.
- Any change inside a fence is DESTROYED: **this skill never touches a diagram or a code
  block.** Diagrams are the diagram skill's; code is the author's.

- **CAUSAL** (exit 1): a consequence the before tied to its cause with "so", "because",
  "since" or "therefore" is in the after with no cause in its sentence. This is the defect
  every cold reader found, round after round — a sentence split at its "so" with the second
  and third consequences left as bare assertions. Re-join it, or say in the report why the
  link is carried some other way.

It also prints the measures before and after and warns when the reading cost rose — an edit
that made a document harder to read is a defect even when it lost nothing.

## Rules that are not negotiable

**The content is the invariant.** Every claim, number, name, path, identifier, cross-reference,
example and caveat in the before is in the after. Shorter is a consequence of clearer, never a
goal: a document may come out the same length or longer where a wall became a list.

**Prose only.** Fences, tables' facts, headings' words and the document's order of sections stay.
A heading may be reworded only with a declaration. Sections are not merged, split or reordered —
that is a restructure, and a restructure is a different request.

**The author's voice stays.** Edward writes, and reads, plainly and directly. Tighten toward
that: short sentences, one idea per paragraph, the point first, lists for enumerations, the
verb doing the work. Never toward a house style he does not have, and never with filler he would
not write ("it is worth noting", "in order to", "leverage").

**Judge by reading, not by counting.** The measures rank the queue; a human reader (or the cold
reader below) decides whether a section reads. A section whose numbers moved and still reads
badly is not done; a section that reads well at 26 words a sentence is.

**Nothing repeats.** *"AI is very enthusiastic about putting down words, but they are often just
duplicative clutter."* Where a paragraph says again what a list or table beside it already says,
the repeat goes — after the gate confirms every fact it carried is still there.

## The two readers

- **The author** — tighten for clarity and concision, fix grammar and consistency, vary rhythm,
  and enforce a style guide, without changing the author's meaning or voice or inventing new
  claims. Where Personetta (`~/.personetta/claude-recipes/`) is installed, its `edit-copyedit`
  recipe carries this judgement; where it is not, apply the same rule directly — it does not
  need the recipe to hold.
- **The cold reader** — the adversary, dispatched as a separate agent with no memory of the
  edit. It reads the before and the after and lists every claim, qualifier, example or caveat
  in the before it cannot find in the after; and separately, every place the after made it
  re-read. Anything on the first list is a refusal, whatever the gate said — the gate finds
  forms, the reader finds meaning. The second list is the next round's queue.

Use the tool to rank, the author to rewrite, the gate to prove no fact left, the reader to prove
no meaning left.

## Working one document

1. **Measure first.** `check <file>`. Read the cost line, the walls, the worst sentences. Copy
   the file to scratch as the before.
2. **Fix in ranked order**, worst section first. For each: split sentences at their joints;
   move the point to the front; turn an enumerating paragraph into a list; break a wall with a
   sub-head only where the source's own words supply one (a lead phrase, a bold term); cut a
   repeat. Every fact stays where a reader can find it.
3. **Re-measure after each section, and `diff` the document.** A section whose cost did not move
   was edited in the wrong place. A DESTROYED is fixed before the next section is touched.
4. **Dispatch the cold reader** over the whole document when the queue is done. Fix what it
   found lost; take what it found hard as the next round.
5. **Report**: cost, words per sentence, long-sentence share, walls and grade before and after,
   per document; the gate's verdict; the cold reader's two lists and what was done about each;
   any section deliberately left alone and why.

Edits land **in place**, on a branch or in a commit of their own, so the diff is the review — the
magazine edition is then rebuilt from the tightened source. The before lives in git; nothing
else needs keeping.

## Working a tree

1. `audit --json` the tree and rank by cost — the documents first, then the sections. Fixture
   and generated directories are excluded with `--exclude`.
2. Report the shape before editing: how many documents, how many words, how many walls, where
   the cost concentrates.
3. Work in ranked order, one document per commit, the gate and the reader on each.
4. Stop when asked; report the queue position.

## "Pre-existing" is not a category

Everything the skill meets is pre-existing by definition; that is what it is for. A hard sentence
is in the queue whether the last round wrote it or the author did. Nothing is left alone because
it was already there, because its section's average scored under a threshold, or because fixing
it looks like the author's job. Edward, on the first run: *"the whole point of the edit skill is
to fix these things. Everything it encounters will be 'preexisting' by definition. Don't let it
stop you."*

So, concretely:

- **A sentence over 45 words is in the queue on its own**, whatever its section's cost. The
  section average hides a 137-word sentence in a section that otherwise reads well.
- **The cold reader's "still hard" list is round two, not a footnote.** Rounds continue until the
  reader's list is empty or holds only items of the last kind below.
- **An undefined term, a reference with no antecedent, a count that does not add up** — the editor
  fixes what the document's own words allow (move the definition next to its first use, name the
  noun the pronoun meant, reconcile the count from the table the document already has). Where the
  fix needs a fact the document does not contain (what "M" stands for, when nothing says), it is
  one line in the report as an authoring question, and the work continues. It is never a reason
  to stop.

## Restraint

- **Leave good writing alone.** A section that reads well is named as kept, not rewritten for
  the sake of a diff — "reads well" judged by the reader, never by the average alone.
- **Do not cut a caveat to make a sentence short.** "unless the run is in flight" is a fact.
- **Do not add.** No new examples, transitions, summaries or headings whose words the source did
  not supply. An "in short" the author did not write is a claim the author did not make.
- **Do not flatten a deliberate long sentence.** A sentence that carries one thought through a
  chain of consequences may be long on purpose; the tell is that splitting it needs a new
  connective the author did not write.
- **A table is not prose.** Cells are facts; they are never reworded without a declaration.

## Which model this needs

The measuring and the gate are code. The rewriting is judgement, and the kind a weaker model
gets wrong in a specific way: it shortens by dropping qualifiers, and the gate cannot see a
dropped "only" or "unless". So the author is Opus or Fable, and the cold reader is a different
instance — never the one that wrote the edit. A cheap model may run `audit` and report the queue.

Pairs with [[diagram]] (figures) and [[magazine]] (pages); this is the third, for the words.
