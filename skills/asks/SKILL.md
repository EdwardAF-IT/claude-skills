---
name: asks
description: Collect every outstanding answer the user owes, one question at a time but back to back with no work in between, then walk him through his own todos (things only he can do, with the exact commands) one at a time, announce clearly when the list is finished, then go apply everything. Works in any repo. Use when he says "asks", "my asks", "ask me my questions", "what do you need from me", "what are my todos", "ask me one at a time", or after a sitrep when he wants to clear the needs-you list.
---

# Asks

The daytime counterpart to the never-block-at-night rule: questions get **parked** while Edward is
away, and drained here while he is at the keyboard.

Three things he has said plainly shape this skill:
- **One question at a time**, never a wall of questions.
- **His todos too, after the questions.** Things only he can do (apply a patch, run a command at his
  keyboard, vote, close a thread, push from a checkout the gate blocks) come one at a time after the
  last question, each with what he needs to finish it fast: the exact commands, paths and links.
- **Collect first, act after.** He cannot sit watching the scroll while work runs between items.
  Ask every question and walk every todo back to back, take no action until the last item is done,
  tell him unmistakably that he is finished, *then* apply everything.

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

### Build the todo list too

From the same sources, collect **his todos**: actions only he can take, not decisions. Typical ones:
a patch to apply to a protected path, a push the agent's gate refuses, a PR to vote on, a thread only
a person can close, a staged merge to commit, a credential or setting to change. Drop any you can do
yourself. For each, gather everything he needs to finish it without looking anything up:

- the exact terminal commands, in run order, with absolute paths, ready to paste (one shell; say
  which: PowerShell or bash);
- the link (PR, work item, file) when there is one;
- how he will know it worked (the output to expect), and what you will do once he says it is done.

Re-check each todo is still needed right before listing it (a PR already voted, a patch already
applied): cheap reads only, and drop the ones already done.

Build both lists **before** the first question, so the counts are known. Tell him up front:
`<N> questions, then <M> todos. Back to back; I do nothing until the last one is done.`

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

## Phase 2 — todos, one at a time

Straight after the last question (no work in between), walk the todos. For each, **one
`AskUserQuestion` call with a single question**:

- Question text starts `Todo 2 of 5:` (the last one `LAST TODO (5 of 5):`), then the task in one
  line and why it matters in one more.
- Put the commands and links in the first option's `preview` (monospace, copyable): the commands in
  run order, the link, and the expected output. Keep it short enough to read at a glance.
- Options: `Done` (first), `Skip for now` (stays on the list, next round), `Won't do` (record it and
  drop it). Add `Tell me more` only when the task genuinely needs explanation.
- If he picks `Tell me more`, answer in at most three lines and re-ask the same todo; that is the
  only talk allowed between items.

Between todos: **no tool calls, no checking his work, no follow-up actions.** Verify and follow up in
Phase 4.

## Phase 3 — announce done

When the last todo is answered, print this, so it is impossible to miss:

```
==================================================
  ✅  ALL DONE — every question (N) and todo (M)
      You can walk away. Applying everything now.
==================================================
```

Follow it with two short numbered lists: each question in a few words → his answer; each todo →
Done / Skipped / Won't do.

## Phase 4 — apply

Only now act, in dependency order: apply the answers, then for every todo marked `Done`, check it
landed (the expected output, the merged commit, the closed thread) and run its follow-up (relaunch
the review, merge the branch, start the unblocked work). A `Done` todo that did not land goes back on
his list for the next round with what went wrong; never redo his part yourself. A skipped todo stays
where it was recorded. Where each answer gets applied depends on its source:

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
`Answered <n> of <N>, todos <m> of <M>`, list the unanswered and unwalked titles (left parked where
they were, never abandoned on his behalf), and go apply what you have.

If there are no questions, go straight to the todos; if there are no todos, the banner says so.

## Rules

- One question or todo per call, always — but no work between calls.
- A todo carries everything needed to do it: commands in run order, absolute paths, the link. He
  should never have to look something up to finish one.
- Never re-ask something already answered this session or already recorded as a decision.
- Ask first; research only to apply an answer. No board queries or "is it still open" checks
  before asking — offer "Already handled" as an option instead.
- Never use this during unattended work — it is the opposite of the night rule.
- Brevity applies here as everywhere: he asks for detail when he wants it.
