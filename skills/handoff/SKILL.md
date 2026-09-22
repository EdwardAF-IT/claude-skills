---
name: handoff
description: End a work session cleanly - write a handoff note the next session can resume from, persist durable learnings to memory, and tell the user how to resume. Use when the user says "handoff", "wrap up", "I'm done for today", or "hand this off"; an argument names the note ("handoff doc-pipeline") so `pickup <name>` finds it. For a snapshot taken while work CONTINUES (leaving overnight with tasks running, or before a compaction mid-run), use the checkpoint skill instead.
---

# Handoff

The user runs long multi-day sessions that get compacted many times. A handoff is a deliberate,
lossless replacement for compaction: capture what the next session needs, then start fresh.

**Not for unattended work.** If the work continues after the user leaves — an overnight run, a
long grind, an approaching compaction mid-run — use the `checkpoint` skill instead. A handoff
says the work is stopping.

## Steps

1. **Collect state** (do not ask the user; derive it):
   - `git status --short` and `git log --oneline -10` in the current repo
   - Any running background tasks, subagents, scheduled wakeups or cron entries (`CronList`) -
     list each with its purpose and whether it survives session end
   - Open questions you were waiting on, and decisions you made without the user
   - The current task/goal and the next 3-5 concrete steps

2. **Write the handoff note** to `docs/handoffs/<yyyy-mm-dd>-<name>.md` inside the repo
   if a `docs/` folder exists, otherwise to `.claude/handoffs/` (lowercase filenames only).
   `<name>` is the argument the user gave (`handoff doc-pipeline`), else a short slug you choose;
   it goes in the banner too, after a middle dot, so `pickup <name>` can find this note among
   the notes other sessions leave in the same folder. Reuse the name a previous handoff or
   checkpoint of the same work used. Structure - keep it under ~80 lines, facts not narrative:

   ```markdown
   # Handoff <yyyy-mm-dd hh:mm> · <name>

   ## Goal
   ## Where things stand
   ## In flight (agents, background tasks, branches, PRs)
   ## Decisions made this session
   ## Open questions for Edward
   ## Next steps (ordered)
   ## Resume command
   ```

3. **Persist durable learnings to memory** - anything true beyond this session (a rule the
   user stated, a trap you hit, a preference). One fact per file, index it in `MEMORY.md`.
   Do NOT put session-specific state (branch names, task numbers) in memory; that belongs in
   the handoff note.

4. **Promote standing rules to CLAUDE.md** - if the user stated a rule that every future
   agent in this repo must follow (including SDK-spawned agents that never see memory),
   propose the exact line to add to the repo's `CLAUDE.md` and add it if the user has
   already approved editing that file this session.

5. **Reply** with: the handoff file path, the one-line resume instruction (`claude --continue` for
   the same session, or `claude` + "pickup <name>" for a fresh one), and any open
   question the user must answer before the next session can proceed unattended. If the day's
   `.claude/checkpoints/` note exists, fold its contents in and say so.

## Rules

- Never end a session with a background task or subagent the handoff note doesn't mention.
- Never call AskUserQuestion during a handoff; record the question in the note instead.
- Filenames lowercase; no AI-attribution trailers if the repo forbids them (check CLAUDE.md).
