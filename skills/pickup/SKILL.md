---
name: pickup
description: Pick up a repo where a previous session left it and keep going as if there had been no break - find the right handoff or checkpoint note, reconcile it with what git and other sessions did since, restore the session's operating state (tools, watches, loops, standing orders) and resume the note's approved next steps. Use when he says "pickup", "pickup <name>", "pick up where we left off", "where were we", "resume", "get up to speed", "read the handoff", "catch me up", or starts a session by pointing at a handoff file.
---

# Pickup

The mirror of [[handoff]] and [[checkpoint]]. The goal is that the new session is in the same
place the old one was: same rules in force, same tools to hand, same watches running, same items
tracked, and moving on the next step, without the user re-explaining anything.

## Steps — derive everything, ask nothing

1. **Find the note** with the finder (looks in `docs/handoffs`, `.claude/handoffs`,
   `.claude/checkpoints`, newest first, with commits and dirty files since the newest):

   ```bash
   python ~/.claude/skills/pickup/scripts/latest.py [name]
   ```

   With `pickup <name>`, the newest note of that name is the note; other names are sibling
   sessions', never merged in. With no name and several recent notes, pick the one whose goal fits
   this session's title and conversation and say which in one line.

2. **Read the whole note**, then every memory file and doc it points at. Adopt its standing
   orders as this session's own; they hold until the user lifts them.

3. **Restore the tools.** Confirm every path in the note's Tools section exists; read each script
   once so its usage is known. If a tool still points at an old scratchpad, use the durable copy
   and say so. A missing tool is a finding in the brief.

4. **Reconcile, item by item.** For each row of the Items table, check its live state cheaply
   (`git -C <path> log -1`, PR status, worktree exists, process alive) and record what changed:
   merged, moved, gone, unchanged. Commits and dirty files the note does not mention belong to
   another session or the user: report them, never touch them. List other sessions on this
   checkout if the session tools offer that. A checkpoint newer than the handoff for the same work
   overrides its "where things stand".

5. **Restore the running state.** Run every Resume step marked `[auto]`, in order: re-arm the
   watches and monitors, restart the loops, re-run checks. Skip any step whose item has since
   changed (merged, gone) and say why. Never run an unmarked step, anything the standing orders
   paused, or new work.

6. **Brief the user** in at most fifteen headline lines:
   - the cwd, if it is not the folder the work lives in (hooks and gates bind at session start);
   - which note, and which sibling notes were passed over;
   - what changed since the note, item by item, and who moved it;
   - what this pickup restored (tools, watches, loops) and anything it could not;
   - standing orders in force;
   - open questions and the user's todos, in the note's order;
   - the next step, and whether it is already under way.

   Then continue with the operating loop the note describes, exactly as the previous session ran
   it. Wait for the user only for steps that are not `[auto]`, need a decision, or were paused.
   Between 21:00 and 07:00 local, self-directed work continues without waiting at all.

## Rules

- **Never change the working directory.** Reach every repo in place: `git -C <repo>`,
  `latest.py --root <repo>`, absolute paths for Read and Grep.
- Never call AskUserQuestion during a pickup; state each ambiguity in the brief with the reading
  chosen.
- Never treat a sibling session's dirty files as abandoned.
- Never delete or move a note; a stale one is reported as stale.
- The brief is a headline per line. He asks for detail when he wants it.
