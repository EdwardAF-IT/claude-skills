---
name: sitrep
description: Brief structured status report - what completed since the last report (with headlines), what agents are doing, satellite health, PRs, open work-item count, an issue summary, and what's needed from the user. Use whenever the user asks for status in any form ("status", "status?", "how's it going", "current status", "where are we", "what's the state of things"), or when reporting in after unattended work.
---

# Sitrep

Edward's standing status format. **He reads this to decide what to do next, not to learn the
history.** He will ask for detail on any line he wants expanded — so every line is a headline,
never a paragraph.

## Hard brevity rules — these are the point of the skill

- Completed headlines: **≤ 12 words each**, plain language, not the issue's own title verbatim
  (his titles are long and hard to scan — compress to the thing that changed).
- Issue entries: **≤ 2 lines**. Line 1 = what broke + status tag. Line 2 (resolved only) = root
  cause + fix.
- Needs-from-you entries: **one line each**, phrased as the decision he must make.
- Whole report fits roughly one screen. If a section would run long, give the count and the top 3,
  then "+N more — ask for the list."
- No preamble, no "great news!", no restating the request. Start at the first heading.
- **Never report on your own plumbing.** A tool that is absent, a CLI not configured for this repo,
  a query you could not resolve — none of that is a finding, an issue, or a caveat for him to read.
  It never appears in the report. "Issues" means problems in *the work*: failed runs, red gates,
  blocked items, broken builds. If a source is missing or ambiguous, silently omit the section it
  would have fed. Report a source as `unavailable` **only** when the repo demonstrably uses it and
  it broke — never when it simply is not part of this repo.

## Where the numbers come from

**Works in any repo.** Discover the sources, never assume a particular stack. A repo with only git
still gets a useful report; richer sources just add sections.

### Always available

| Section | Source |
|---|---|
| Since-last-report window | `.claude/status/last-sitrep.json` (ISO-8601 **with offset**). Missing → last 24h. **Write the new timestamp only after a successful report.** |
| Completed | commits in the window (`git log --since`), merged branches, plus what this session finished |
| Agents | subagents, background tasks, scheduled wakeups and cron entries this session owns |
| Issues / Needs you | this session's own state, plus open items in `.claude/checkpoints/<date>.md` and recent handoff notes |

### Added when detected — check in this order

1. **The repo's `CLAUDE.md` has a `## Status sources` section** → use the commands it names, in
   preference to anything below. This is how a repo teaches its specifics once; it travels with the
   checkout, so worktrees and dispatched agents get it too.
2. **`maestro` on PATH and this checkout is a registered consumer** → `maestro runs list` for
   agents, `maestro decisions list` (unresolved) for needs-you, `maestro ledger list` for the board
   on a structured-file consumer. From `C:\Code\maestro` the consumer is `dogfood-gh`; if a command
   says the registry is empty you are in the wrong checkout — fall back, don't report it as a finding.
3. **GitHub remote** → `gh issue list --state closed --json number,title,closedAt` filtered to the
   window for completed; `--state open` count for open work items; `gh pr list --json
   number,title,isDraft,statusCheckRollup` for PRs with check status.
4. **Azure DevOps remote** → the repo's own CLI, or `az boards` if configured.
5. **Flat task file** (`tasks.md`, `TODO.md`, a backlog folder) → count open, diff against the window.
6. **Test fleet / satellites** → only if the repo has such scripts (e.g. `eng/satellite/`). Say
   "unknown" rather than guessing, and omit the section entirely in repos that have no fleet.

Run the read-only queries in parallel; never let one broken query sink the report.

**Section inclusion — decide per section, before writing anything:**

| Situation | What appears |
|---|---|
| The repo uses this source and it returned data | the section, with the data |
| The repo uses this source and it genuinely returned zero | the section, with `0` / `none running` |
| The repo has no such source at all | **nothing — omit the heading entirely** |
| A query returned empty and you cannot tell whether that means zero or misconfigured | **omit the section.** Never print the number with a caveat attached |
| The repo demonstrably uses this source and it errored | `unavailable — <six-word reason>` |

A quiet repo should produce a short report — completed, agents, needs-you — and nothing else.
Empty scaffolding is the failure mode to avoid.

### The window label

Store and compare timestamps with an explicit offset, and **render the window in his local time**
— never print a bare clock time that came from a UTC string. Label it so it is unambiguous at a
glance: `since yesterday 21:40`, `since Tue 09-16`, `since your last report 8 min ago`.

If the last marker is **under an hour old** (usually back-to-back reports), say so plainly and
widen the useful context rather than reporting an empty window as if nothing were happening:
`Nothing since your last report 8 min ago. Last activity: <most recent commit/run, with its date>.`

## Format

```markdown
## Completed since <time> — <N>
- #1383 satellite build failures now fail the gate immediately
- #1381 Podium lane pickers show per-lane guidance

## Agents
- <n> running: <item> (<lane>, <how long>) — one line each; flag anything stalled
- idle / none running

## Satellites                                (omit in repos with no test fleet)
host-a ok · host-b ok · host-c down (<six-word reason>)

## PRs — <N> open
- #<n> <title> — checks green / RED / draft

## Open work items: <N>                       (omit if the repo has no task system)

## Issues
- <what broke> — BLOCKED / being fixed / resolved
  root cause: <brief> · fix: <brief>          (resolved only)

## Needs you — <N>
1. <the decision, one line>
2. <...>
```

Omit any section that is genuinely empty except **Needs you**, which always appears (say "nothing"
when there is nothing).

## After the report

End with one line: `Ask for detail on any line, or run /asks to work the needs-you list one at a
time.` Then stop — do not start new work off the back of a status report unless he says so.

During unattended runs, never let a sitrep become a stopping point: report and keep going.
