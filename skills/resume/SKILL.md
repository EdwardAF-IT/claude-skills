---
name: resume
description: Pick up a repo where a previous session left it - find the right handoff or checkpoint note for this checkout, reconcile it with what git and the other live sessions have done since, and brief the user in a few lines before touching anything. Use when he says "resume", "resume <name>", "pick up where we left off", "where were we", "get up to speed", "read the handoff", "catch me up", or starts a session by pointing at a handoff file.
---

# Resume

The mirror of [[handoff]] and [[checkpoint]]. Several sessions work the same repo, each writes
its own note, and the notes pile up in two folders; the one at the top of the list is not
necessarily this session's. A resume finds the right note, says what has moved since it was
written, and names the other sessions on this checkout — then stops and waits.

## Steps — derive everything, ask nothing

1. **List the candidate notes** with the finder; it looks in `docs/handoffs`, `.claude/handoffs`
   and `.claude/checkpoints`, newest first, and shows the commits and dirty files git has seen
   since the newest one:

   ```bash
   python ~/.claude/skills/resume/scripts/latest.py [name]
   ```

   Every handoff and checkpoint carries a name in its banner (`# Handoff <date> · <name>`). With
   `resume <name>` the finder returns the newest note of that name and that is the note; the
   other names in the listing are sibling sessions', reported as such and never merged in. With
   no name and several recent notes, list the names and pick the one whose goal fits this
   session's title and recent conversation, saying which and why in one line; a bare `resume`
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
     (`git branch`, `CronList`, `gh pr view`) and report what did not survive
   - a checkpoint newer than the handoff for the same work overrides the handoff's "where things
     stand"; say which note won

4. **Brief the user**, under fifteen lines:
   - which note was used, and which others were passed over and whose they are
   - goal, where things stand, in flight (only what still exists)
   - what moved since the note, and who moved it
   - open questions, in the note's order
   - the next step the note proposes

   Then stop. Do not start the next step until the user says so — except between 21:00 and 07:00
   local, when [[nights-are-for-work-days-are-edwards]] applies: take the first next step and
   record it.

## Rules

- Never call AskUserQuestion; every ambiguity is stated in the brief with the reading chosen.
- Never treat a sibling session's dirty files as abandoned; they are theirs until that session's
  note or the user says otherwise.
- Never delete or move a note. Old notes are history; a stale one is reported as stale, not
  cleaned up.
- The brief is a headline per line. He asks for detail when he wants it.
