---
name: asks
description: Work through everything outstanding that needs the user's input, one question at a time, applying each answer before moving to the next. Works in any repo. Use when he says "asks", "my asks", "ask me my questions", "what do you need from me", "ask me one at a time", or after a sitrep when he wants to clear the needs-you list.
---

# Asks

The daytime counterpart to the never-block-at-night rule: questions get **parked** while Edward is
away, and drained here while he is at the keyboard. He has said explicitly he wants them **one at a
time** — never a wall of questions.

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
     This is the intended way to teach a repo's specifics once; prefer it over guessing.
   - `maestro` on PATH and this checkout is a registered consumer →
     `maestro decisions list -c <consumer>`, unresolved only (`decisions show <id>` for detail).
   - A GitHub remote → `gh issue list --search "..."` for items labelled/assigned as needing a
     decision, and PRs with review requested.
   - An Azure DevOps remote → the repo's own CLI or `az boards` if configured.
   - A flat task file (`tasks.md`, `TODO.md`, a backlog folder) → entries marked blocked/needs-input.
   - None of the above → skip silently. Do not report "no task system" as a finding.

Drop anything already answered, superseded, or that you can decide yourself — **if you can make the
call and record it, do that instead of asking.** Say how many you dropped and why, in one line.

Tell him the count up front: `<N> things need you. Starting with the one blocking the most work.`

## Ask them one at a time

For each item, **one `AskUserQuestion` call with a single question**:

- Context first, **≤ 2 lines**: what is blocked and what it costs.
- Options as concrete choices, not open prose. Put your recommendation first, labelled
  `(Recommended)`, with the reason in the description.
- Never batch two questions into one call. Never move on before the answer is applied.

**Apply the answer immediately**, before asking the next one. Where it gets applied depends on
where it came from:

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

Confirm each in **one line** (`#1337 ruled pass — applied`), then go straight to the next question.

## Stopping and finishing

He can stop at any point ("that's enough", "later"). When he does, or when the queue is empty:

- Report: `Answered <n>. <m> left.` — plus the one-line titles of what remains.
- Leave the unanswered ones parked where they were; never mark them abandoned on his behalf.
- If answers unblocked work, say what is now dispatchable — then ask once whether to start it.

## Rules

- One question per call, always. This skill exists because batching is what he does not want.
- Never re-ask something already answered this session or already recorded as a decision.
- Never use this during unattended work — it is the opposite of the night rule.
- Brevity applies here as everywhere: he asks for detail when he wants it.
