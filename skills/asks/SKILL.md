---
name: asks
description: Collect every outstanding answer the user owes, one question at a time but back to back with no work in between, announce clearly when the last one is answered, then go apply them all. Works in any repo. Use when he says "asks", "my asks", "ask me my questions", "what do you need from me", "ask me one at a time", or after a sitrep when he wants to clear the needs-you list.
---

# Asks

The daytime counterpart to the never-block-at-night rule: questions get **parked** while Edward is
away, and drained here while he is at the keyboard.

Two things he has said plainly shape this skill:
- **One question at a time**, never a wall of questions.
- **Collect first, act after.** He cannot sit watching the scroll while work runs between
  questions. Ask every question back to back, take no action until the last answer is in, tell him
  unmistakably that he is done, *then* apply the answers.

Works in any repo. Nothing below is required for the skill to be useful — a repo with no task
system at all still has parked notes and this session's own open questions.

## Build the queue

Walk this ladder, skipping what does not apply. Steps 1–2 always work; 3 is best-effort.

1. **This session** — anything you are waiting on, plus decisions you deferred rather than made.
2. **Parked notes in this repo** — open questions in the most recent notes
   `python ~/.claude/skills/pickup/scripts/latest.py` finds (checkpoints and handoffs), not yet
   struck through.
3. **The repo's task system**, if it has one — detect, do not assume:
   - The repo's `CLAUDE.md` has a `## Status sources` section → **use the commands it names**.
   - `maestro` on PATH and this checkout is a registered consumer →
     `maestro decisions list -c <consumer>`, unresolved only (`decisions show <id>` for detail).
   - A GitHub remote → `gh issue list --search "..."` for items needing a decision, and PRs with
     review requested.
   - An Azure DevOps remote → the repo's own CLI or `az boards` if configured.
   - A flat task file (`tasks.md`, `TODO.md`, a backlog folder) → entries marked blocked/needs-input.
   - None of the above → skip silently. Do not report "no task system" as a finding.

Drop anything already answered, superseded, or that you can decide yourself — **if you can make the
call and record it, do that (later, in the apply phase) instead of asking.** Say how many you
dropped and why, in one line.

Build the whole queue **before** the first question, so N is known. Tell him up front:
`<N> questions. I'll ask them back to back and do nothing until the last one is answered.`

## Phase 1 — ask, back to back

For each item, **one `AskUserQuestion` call with a single question**:

- Start the question text with its position: `Question 3 of 7:`. The last one starts
  `LAST QUESTION (7 of 7):`.
- Context first, **≤ 2 lines**: what is blocked and what it costs.
- Options as concrete choices, not open prose. Recommendation first, labelled `(Recommended)`, with
  the reason in the description. Offer "Already handled" where it might be.

Between questions: **no tool calls, no research, no applying, no commentary** beyond at most one
line acknowledging the answer. Go straight to the next question. Record answers in your own working
notes only.

If an answer changes a later question (makes it moot or changes its options), adjust or drop that
question without doing any work — and keep the `k of N` count honest (renumber if N changes).

## Phase 2 — announce done

When the last answer is in, print this, so it is impossible to miss:

```
==================================================
  ✅  ALL DONE — that was every question (N of N)
      You can walk away. Applying the answers now.
==================================================
```

Follow it with a short numbered list: each question in a few words → his answer.

## Phase 3 — apply

Only now act on the answers, in dependency order. Where each gets applied depends on its source:

| Source | Apply with |
|---|---|
| a parked note | make the change, then strike the line from the note |
| this session | just act on it |
| `maestro` question | `maestro decisions answer` |
| `maestro` ac-ruling | `maestro decisions rule`, then `apply-ac-ruling` |
| `maestro` ac-draft | `decisions approve` / `reject`, then `apply-ac-draft` |
| `maestro` grooming-draft | `decisions approve-grooming` / `reject-grooming` |
| another task system (step 3) | its own resolve/answer verb — the command its `CLAUDE.md` or CLI names |
| no longer wanted | `maestro decisions abandon`, or that system's own "won't do" verb — recorded, never silent |
| anything else | whatever that system's own write path is — never edit its store by hand |

Apply the answers without asking anything further. If applying one turns up a genuinely new
decision, park it (it goes in the next round); do not interrupt him with it. Finish with one line
per answer (`#1337 ruled pass — applied`) and what is now unblocked and already started.

## Stopping early

He can stop at any point ("that's enough", "later"). Then print the done banner with
`Answered <n> of <N>`, list the unanswered titles (left parked where they were, never abandoned on
his behalf), and go apply the answers you have.

## Rules

- One question per call, always — but no work between calls.
- Never re-ask something already answered this session or already recorded as a decision.
- Ask first; research only to apply an answer. No board queries or "is it still open" checks
  before asking — offer "Already handled" as an option instead.
- Never use this during unattended work — it is the opposite of the night rule.
- Brevity applies here as everywhere: he asks for detail when he wants it.
