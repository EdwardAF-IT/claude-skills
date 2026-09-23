---
name: pickup
description: Pick up a repo where a previous session left it - find the right handoff or checkpoint note for this checkout, reconcile it with what git and the other live sessions have done since, and brief the user in a few lines before touching anything. Use when he says "pickup", "pickup <name>", "pick up where we left off", "where were we", "resume", "get up to speed", "read the handoff", "catch me up", or starts a session by pointing at a handoff file.
---

# Pickup

The mirror of [[handoff]] and [[checkpoint]]. Several sessions work the same repo, each writes
its own note, and the notes pile up in two folders; the one at the top of the list is not
necessarily this session's. A pickup finds the right note, says what has moved since it was
written, and names the other sessions on this checkout — then stops and waits.

## Steps — derive everything, ask nothing

1. **List the candidate notes** with the finder; it looks in `docs/handoffs`, `.claude/handoffs`
   and `.claude/checkpoints`, newest first, and shows the commits and dirty files git has seen
   since the newest one:

   ```bash
   python ~/.claude/skills/pickup/scripts/latest.py [name]
   ```

   Every handoff and checkpoint carries a name in its banner (`# Handoff <date> · <name>`). With
   `pickup <name>` the finder returns the newest note of that name and that is the note; the
   other names in the listing are sibling sessions', reported as such and never merged in. With
   no name and several recent notes, list the names and pick the one whose goal fits this
   session's title and recent conversation, saying which and why in one line; a bare `pickup`
   with one recent note takes it.

2. **List the other sessions on this checkout** — `list_sessions` from the session tools, filtered
   to the same `cwd`. Each one is a candidate owner of dirty files and of commits the note does
   not mention. Name them by title with their last activity. If the tool is not available, say so
   in one line and rely on git.

3. **Reconcile the note against the tree**:
   - commits since the note's timestamp that it does not mention → "landed since, by <session or
     unknown>"
   - dirty files the note does not claim → "another session's work in progress; not touched"
   - branches, agents, cron entries or PRs the note says are in flight → check each still exists
     (`git -C <repo> branch`, `CronList`, `gh pr view -R <owner/repo>`) and report what did not
     survive
   - a checkpoint newer than the handoff for the same work overrides the handoff's "where things
     stand"; say which note won

4. **Brief the user**, under fifteen lines:
   - **where this session is standing** — the cwd — whenever it is not the folder the note's work
     lives in, plus what that costs (a repo's hooks and gates load at session start and follow the
     session even if the directory moves). One line, first. The app does not always open a session
     in the folder that was picked, so this is a fact to state, never an assumption.
   - which note was used, and which others were passed over and whose they are
   - goal, where things stand, in flight (only what still exists)
   - what moved since the note, and who moved it
   - open questions, in the note's order
   - the next step the note proposes

   Then stop. Do not start the next step until the user says so — except between 21:00 and 07:00
   local, when self-directed work continues without waiting on him: take the first next step and
   record it.

## Rules

- **Never change the working directory** — not with `cd`, not with the directory tool. A `cd`
  inside a Bash call moves the session there for good, and a pickup reads several repos — the note's, the sibling sessions', the one the work
  is about. Reach every one of them in place: `git -C <repo> ...`, `latest.py --root <repo>`,
  absolute paths for Read and Grep. The session ends the pickup where it started it. If the work
  genuinely belongs in another folder, say so in the brief and let the user move.
- Never call AskUserQuestion; every ambiguity is stated in the brief with the reading chosen.
- Never treat a sibling session's dirty files as abandoned; they are theirs until that session's
  note or the user says otherwise.
- Never delete or move a note. Old notes are history; a stale one is reported as stale, not
  cleaned up.
- The brief is a headline per line. He asks for detail when he wants it.
