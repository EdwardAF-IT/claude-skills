---
name: checkpoint
description: Snapshot the current session state to a rolling note, then immediately keep working. Use when the user says "checkpoint", "cp", "snapshot", or is leaving while work continues (an argument names the note, "checkpoint doc-pipeline", matching the handoff it continues); also self-invoke during long or unattended runs before the context fills, after finishing a work item, and before starting anything long-running. Unlike handoff, this never ends the session.
---

# Checkpoint

A checkpoint is a **cheap, repeatable snapshot taken while work continues**. It exists so a
compaction, a crash, or a morning "where did this get to?" costs nothing. It is not a handoff:
never end the session, never suggest ending it, never stop for input.

Use [[handoff]] instead when the work is actually stopping.

## When to take one

- The user says "checkpoint" / "cp" / "snapshot", or is leaving while work continues
- **Self-invoke, without being asked**: before the context fills enough to compact, after each
  completed work item during a long run, and before kicking off anything long-running
- At the start of an unattended stretch, so there is a known-good state from the moment they left

## Steps — keep this fast, under a minute

1. **Collect state** (derive it, never ask):
   - `git status --short`, `git log --oneline -5`, current branch
   - Running background tasks, subagents, scheduled wakeups, cron entries
   - The work item in flight and what is left on it
   - Decisions made since the last checkpoint, and any question that is now parked

2. **Write the note** to `.claude/checkpoints/<yyyy-mm-dd>-<name>.md` in the current repo — an
   **untracked** location, so a long run never spams a gated repo with commits. `<name>` is the
   argument given, else the name of the handoff this work continues, else omitted. Overwrite the
   same file on every checkpoint that day; it is a rolling "current state", not a journal. The
   banner carries the name after a middle dot so `resume <name>` finds it. Keep it under ~40 lines:

   ```markdown
   # Checkpoint <yyyy-mm-dd hh:mm> · <name>

   ## Working on
   ## Done since last checkpoint
   ## In flight (agents, background tasks, branches, PRs)
   ## Decisions taken without the user
   ## Parked questions (NOT blocking)
   ## If resuming cold, do this next
   ```

   If `.claude/checkpoints/` is not covered by the repo's `.gitignore`, mention it once and move on.

3. **Save a durable learning to memory only if one actually appeared** this stretch — a rule the
   user stated, a trap hit. Skip otherwise; a checkpoint is not a memory-writing ceremony.

4. **Reply in one line** — the file path and what you are resuming — then **immediately continue
   the work.** Do not wait for acknowledgement.

## Rules

- Never call AskUserQuestion from a checkpoint. Park the question in the note and keep going.
- Never treat a checkpoint as a stopping point or a place to summarize the whole session.
- Never commit the checkpoint file or run a repo gate for it.
- If a checkpoint reveals a stalled agent or a dead background task, fix it and note it — do not
  leave it for the user to find in the morning.
