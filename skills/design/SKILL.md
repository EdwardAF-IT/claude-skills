---
name: design
description: Run a deep design or assessment pass on a question without switching the whole session's model - dispatches it to a Fable agent with full history, writes a proposal into the repo, and reports back briefly. Use when he says "design", "propose", "assess", "think through", "ask Fable", "what's the right approach for", or asks for a design proposal, architecture assessment or options comparison. Never implements anything.
---

# Design pass

Edward reaches for Fable when he wants real design thinking. He has been doing it by switching the
whole session with `/model fable`; this dispatches instead, so the session keeps its own model and
context.

**This skill never implements.** It produces a proposal to read and decide on.

## 1. Brief the designer with the whole arc, not the question

This is the step he corrects most often. His words: *"make sure it understands the history ... from
the very beginning, the struggles ..., the optimizations you scripted, the expansion ..., the issues
we now see in front of us ... make sure it has enough information."* And on a follow-up round:
*"share with Fable all the information that has transpired between us and his chat since it produced
its original design ... so that it's up to speed."*

So the prompt carries:

- **The history that produced the problem** — what was tried, what broke, what was worked around,
  in order. Not a summary of the current symptom.
- **Everything since the last design round**, when there was one, including his own reactions to it.
- **His concerns in his own words**, quoted, not paraphrased into requirements.
- **Repo paths to read**, not pasted file contents — and an instruction to read before proposing.

A thin brief is the main cause of a design pass he has to send back.

## 2. What the proposal must do

- **Design the long-term solution first, then extract the short term from it as a proper subset.**
  His standing rule: *"I don't want to do something now that is going to end up causing us a lot of
  misery ... because of some kind of stupid hackneyed approach that we end up ripping out anyway ...
  I want the short term solution to be a subset of the long term solution so that whatever work we
  do now gets used later."* Name the shortest first build explicitly, and show it is a subset.
- **Challenge whether the thing is even one component.** He watches for god classes: *"I want to
  make sure that we don't build a god class here ... if a smarter design is to split those apart
  into focused units (SRP), then I'd rather do that. Maybe the 'coordinator' is more of a concept
  than a single class?"* A section that asks "is X a component, or a concept?" and then enumerates
  **the units** with one responsibility each is the shape he approves.
- **Enumerate the actors and objects, and say what might be missing.** He asks this every round:
  *"Are there other important actors or objects that need to be categorized and considered?"* Answer
  it before he has to ask.
- **Check the design against where the product is going, not where it came from.** He caught one
  pass assuming an overnight batch model when the direction had moved to a continuously running
  system with an operator window. State the assumption about the current direction out loud so a
  wrong one is visible.
- **Hunt the implied behavior nothing implements yet.** *"Look for this and any other implied
  behavior that may still need to be designed and implemented in order to deliver the promise of
  what the screens show."* Any artifact that promises behavior — a screen, a CLI verb, a doc — is
  a source of requirements that may have no code behind it.
- **Cover failure modes, state and configuration, and the operator surface.** These are sections in
  every design he has accepted.

## 3. Shape of the document

Follow the repo's existing design docs. In maestro, `docs/design/` is the house style and reads:
descriptive title (what it *is*, not "design for X") → **how it works, in plain steps** near the top
→ the framing question → problem and goals → is it a component? → the units → the pipeline → rules
and evidence → escalation → state, storage, configuration → operator commands → what the live
window shows → fit with the stages and the shortest first build → failure modes → operator surface.

- **Diagrams are required.** *"Please add some WELL DONE diagrams to the design doc that clearly
  explain how it will work."* Mermaid, one idea per diagram, with a sentence of reading under each.
  A wall of prose explaining a flow is a defect.
- **Length follows substance, but nothing repeats.** These documents legitimately run long; what he
  objects to is padding: *"AI is very enthusiastic about putting down words, but they are often just
  duplicative clutter."* Say each thing once, in the place it belongs.
- **Open questions are a list**, never buried in prose.
- Write it into the repo (`docs/design/` in maestro, else the repo's equivalent), lowercase
  filename, never a session temp folder.

## 4. After the proposal

- **No work breakdown until he has approved the design.** *"Let me review the design first. No need
  to waste effort on a WBS if design changes make it change."* Do not file tasks or issues off an
  unreviewed proposal.
- **Report back in under ten lines**: the recommendation, the one thing that would change it, the
  file path. He reads the document; the chat line is a pointer.
- If it needs a decision from him, park it for [[asks]] rather than stopping the session. Never ask
  between 21:00 and 07:00.
- **Offer the reading copy.** He repeatedly asks for design docs as *"easy to read magazine or
  desktop-publishing style documents that I can print and read in the comfy chair"* — colorful,
  body text serif 10pt. If the repo already has that machinery (in maestro:
  `docs/research/magazine/magazine.css` and `build-digest.mjs`, printed through headless Chromium),
  use it rather than inventing a layout. Offer once; don't build it unasked.

## Review rounds

When he asks for a review round rather than a single design, his preferred shape is four personas —
architecture, lead dev, SDET, coherence — dispatched as four agents over the same target, whose
findings become ledger items, remediating the foundational ones first.
