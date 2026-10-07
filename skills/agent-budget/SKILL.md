---
name: agent-budget
description: Edward's points budget for concurrent subagents - haiku 1, sonnet 2, opus 3, fable 4, +0.5 for thinking - summed across every live agent and capped by the budget in ~/.claude/agent-budget.json. Use BEFORE launching or resuming any subagent, when the user changes the budget ("set the budget to N", "raise/lower the agent budget"), when asked how much budget is in use, and whenever deciding what to run next.
---

# Agent budget

Edward caps concurrent subagents by **points**, not by count. He should never have to restate this.

## The points

| Model tier | Points | With thinking / high effort |
|---|---|---|
| Haiku | 1 | 1.5 |
| Sonnet | 2 | 2.5 |
| Opus | 3 | 3.5 |
| Fable | 4 | 4.5 |

Map subagent types by the model they run: `maestro-haiku` = Haiku; `maestro-sonnet` = Sonnet;
`maestro-sonnet-hi` = Sonnet with thinking (2.5); `maestro-opus` = Opus with thinking (3.5);
`maestro-fable` = Fable with thinking (4.5); `general-purpose`/`Explore`/`claude` = whatever model they
were given (the session's model if none). Workflows count every agent they run concurrently.

## The budget

The current budget lives in `~/.claude/agent-budget.json` (`budget`, `setBy`, `setOn`, `reason`,
`standing`). Read it every time; never rely on a remembered number. When Edward changes it, update that
file (budget, setBy, setOn, reason) and confirm in one line: `Agent budget now N points (was M).`
`standing` is the normal cap to return to when a temporary limit ends.

## Before launching or resuming any agent

1. Read the budget file.
2. Sum the points of every agent still running (live background agents, running workflow agents).
   A stopped agent counts again the moment it is resumed.
3. Add the new agent's points. Launch only if the new total is **<= budget**.
4. Otherwise do not launch. Queue it, and start it when finished agents bring the total down far enough.

## When over budget (the budget was lowered, or agents were resumed)

- **Never stop, kill or pause a running agent to get under the line.** That throws away the work it
  has done. Let every running agent finish.
- Start nothing new until the running total is <= budget.
- Resuming an agent that was stopped by mistake is finishing existing work, not new spend: do it.

## Choosing what runs next

When a slot frees, start the highest-impact item that fits: engine unblockers and P1s before hygiene;
work that lets the engine run on free lanes before work that only a paid agent can do. Prefer the
cheapest tier that can do the job (Haiku for mechanical edits, Sonnet for most fixes); reserve Fable for
engine-critical changes.

## Reporting

When asked, or when a launch is deferred, say it in one line:
`Budget: 21.5 of 6 points in use (7 agents); nothing new starts until under.`
