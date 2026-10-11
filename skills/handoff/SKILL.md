---
name: handoff
description: End a work session cleanly - write a handoff note the next session can resume from with no lost rhythm (state, per-item table, the operating loop, re-arm commands, durable copies of the session's tools), persist durable learnings to memory, and tell the user how to resume. Use when the user says "handoff", "wrap up", "I'm done for today", "hand this off", or wants to start a fresh session to save tokens; an argument names the note ("handoff doc-pipeline") so `pickup <name>` finds it. For a snapshot taken while work CONTINUES (leaving overnight with tasks running, or before a compaction mid-run), use the checkpoint skill instead.
---

# Handoff

The user runs long multi-day sessions. A handoff is a deliberate, lossless replacement for
compaction: the next session must land in the same place and keep going, as if there had been no
break. His measure of a good handoff is that pickup needs no questions and no re-discovery.

What got lost before, and must not again:
- **The session's own tools.** Scripts written to the session scratchpad die with the session (the
  path contains the session id). The next session cannot find them.
- **The rhythm.** What the session was doing on every event (which log it watched, what it ran
  when a review failed, which loop relaunched what), not just what had happened.
- **Per-item state.** "Several PRs in review" is useless; each item needs its own row with its
  location, state, blocker and next action.

**Not for unattended work.** If work continues after the user leaves, use `checkpoint`.

## Steps — derive everything, ask nothing

1. **Collect state.**
   - `git status --short` and `git log --oneline -10` in every repo touched.
   - Every running background task, subagent, monitor, scheduled wakeup or cron entry: purpose,
     whether it survives the session end (detached OS processes do; monitors, in-session agents and
     `run_in_background` shells do not), and the exact command that re-creates it.
   - Every in-flight item (PR, branch, worktree, agent build, staged merge, proof): id, absolute
     path, state, blocker, next action.
   - Standing orders in force today (freezes, exceptions, pauses, quota limits) with who said them.
   - The user's pending todos, each with its one-line run command.
   - Decisions made this session, and open questions.

2. **Preserve the tools.** Copy every script the session wrote to its scratchpad (or any temp
   folder) that the work still depends on into a durable folder beside the note:
   `<notes folder>/tools/<name>/` (e.g. `docs/handoffs/tools/maestro/`), or the repo's data folder
   when the repo has one. Fix paths inside them that point at the old scratchpad. List each with
   one line on what it does. Copy logs the next session must keep reading (a queue log) and say
   where the live one is.

3. **Write the note** to `docs/handoffs/<yyyy-mm-dd>-<name>.md` if a `docs/` folder exists, else
   `.claude/handoffs/` (lowercase). `<name>` is the user's argument or the name a previous note of
   the same work used. Facts, not narrative; as long as it needs to be, nothing repeated:

   ```markdown
   # Handoff <yyyy-mm-dd hh:mm> · <name>

   ## Goal
   ## Standing orders in force            (rule · who said it · when it lifts)
   ## Where things stand                  (3-6 lines)
   ## Items                               (table: id | path | state | blocker | next action)
   ## Running when this was written       (what · survives? · re-arm command)
   ## The operating loop                  (on <event> → do <exact command>; the session's rhythm)
   ## Tools                               (durable path · what it does)
   ## Decisions made this session
   ## Open questions for the user
   ## User's todos                        (task · one-line run command)
   ## Resume                              (ordered: the exact commands pickup runs first, marked
                                           [auto] when pickup may run them without asking)
   ```

   **Resume** is the part pickup executes. Mark a step `[auto]` only when it restores what was
   already running or approved (re-arm a watch, restart a loop the user approved, re-run a check);
   never for new work, anything outward-facing, or anything the user had paused.

4. **Cold-read check.** Re-read the note as a stranger would: every path absolute and existing,
   every id resolvable, every command runnable as written, nothing that only makes sense with this
   conversation in mind. Fix what fails before replying.

5. **Persist durable learnings to memory** (rules, traps, preferences true beyond this session).
   One fact per file, indexed in `MEMORY.md`. Session state stays in the note.

6. **Promote standing rules to CLAUDE.md** when the user stated one every future agent must follow:
   propose the exact line; add it only if editing that file was already approved this session.

7. **Reply** with the note path, the resume line (`claude --continue` for the same session, or
   `claude` + "pickup <name>" for a fresh one), what will stop when this session ends, and any
   question the user must answer first. Fold in the day's `.claude/checkpoints/` note if one exists.

## Rules

- Never end a session with a background task, monitor or subagent the note does not list with its
  re-arm command.
- Never leave a tool the work depends on only in a scratchpad or temp folder.
- Never call AskUserQuestion during a handoff; record the question in the note.
- Filenames lowercase; no AI-attribution trailers if the repo forbids them.
