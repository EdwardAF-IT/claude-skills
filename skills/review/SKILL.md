---
name: review
description: Run a review board over a codebase - up to eight reviewer personas (architect, developer, sdet, coherence, operability, deletability, suite, coldread), each dispatched as its own agent, findings verified adversarially, deduped across personas, sorted foundational-first, and recorded so a later round never re-raises settled ground. Use when he asks for a review, a review board, a review round, a code review of a whole tree, or names any single reviewer. Not for reviewing one diff or PR - that is /code-review.
---

# Review board

Edward has run this by hand for months, pasting long prompts. The personas live in Personetta,
where he maintains them; this skill is the machinery around them — scoping, dispatch, verification,
dedup, and the memory that stops round twelve repeating round one.

**His standard, in his words:** *"I am obsessed with writing good code and maintainable code as
though I had written it myself, and I proceed always under the assumption that one day I will have
to personally go in and maintain every line of code that gets written by an agent. So I don't want
any slop in there."* A plausible-but-wrong finding costs him more than a missed one. Verification is
not optional.

## `--help`

When the args are `--help`, `-h`, `help`, or `?`, print this and do nothing else:

```
/review [personas...] [flags]      Review board over the current repo

COST, up front: a 3-persona round measured 384,402 tokens and ~14 minutes
sequential (2026-09-19). The full eight extrapolates to roughly 900K-1.1M
tokens and 35-45 minutes. The default is still the full board — pass --core
for the cheap four when the round does not warrant all eight.

PERSONAS   (none named = the full eight, which is the default on purpose.
            --core = architect, developer, coherence, sdet)
  architect       boundaries, coupling, whether this can change without rippling
  developer       DRY/SRP/SOLID/YAGNI, magic constants, god classes, duplication
  sdet            missing edge/negative/error cases, entry-point coverage
  coherence       one concept implemented N ways that agree by luck
  operability     at 3am, can you tell what happened
  deletability    what can be removed, with the evidence that proves it safe
  suite           what a green run actually proves, and what it costs
  coldread        can a stranger understand this in five minutes

SCOPE
  --scope <path>        limit to a subtree (repeatable)
  --since last          only what changed since the last recorded round
  --since <ref>         only what changed since a git ref

MODELS
  --model <name>        override the model for every persona this round
  --model <p>=<name>    override one persona   (--model coldread=opus)
  --effort <level>      low | medium | high | xhigh
  --cheap               every persona one tier down
  --deep                every persona one tier up

SEEING WHAT YOU WILL GET
  --show                for each selected persona: the recipe, model, effort,
                        scope, and its full "You Should" list. Dispatches nothing
  --show-full           print the entire composed persona body that would be
                        sent — the exact text, the way a pasted prompt would read
  --where               just the file paths of the recipes that would be used

RUN CONTROL
  --core                 the cheap four (architect, developer, coherence, sdet)
  --budget <n>           run at most N personas this round, highest value first
  --parallel              dispatch concurrently (default is one at a time)
  --restart               abandon an incomplete round and start fresh
  status                  show progress of the current or last round
  --help                  this text

Defaults: architect, coherence, operability, sdet on Fable; developer on Opus;
suite, deletability, coldread on Sonnet. Sequential. Findings written to
docs/reviews/<date>/ as each persona finishes, so stopping never loses
completed work.
```

## Persona table

| Name | Personetta recipe | Default model | Notes |
| --- | --- | --- | --- |
| architect | `review-architecture` | fable | Structure, not code. Language-agnostic |
| developer | the repo's language review recipe (`review-csharp`, `review-python`, `review-powershell`, `review-javascript`, `review-tsql`) | opus | **Language-specific by design** — see below |
| sdet | `review-testability` | fable | Testedness and testability of the code |
| coherence | `review-coherence` | fable | Whole tree, never a diff |
| operability | `review-operability` | fable | Failures that have not happened yet |
| deletability | `review-deletability` | sonnet | Evidence-gathering |
| suite | `review-tests` | sonnet | The suite as an asset. Measurement first |
| coldread | `review-readability` | sonnet | **Starve its context deliberately** |

**The developer persona is language-scoped on purpose.** Clean-code principles are universal;
idiom is not. The language recipes already carry both — `review-csharp` composes `code-reviewer`
(which states DRY, SRP, SOLID, YAGNI, KISS, no magic constants, Clean Code and Code Complete
explicitly) with `csharp-developer` (nullable reference types, `CancellationToken` propagation,
`ValueTask`, records, pattern matching, `ILogger<T>` message templates, the Options pattern,
`IDisposable`/`IAsyncDisposable`, `Directory.Build.props`, warnings-as-errors) and
`csharp-formatting-standards`. Pick the recipe matching the tree's dominant language; for a
mixed repo, run `developer` once per major language and say which paths each covered.

**The developer persona carries `maintainability-focused` as a mixin baked into the recipe** —
`review-csharp`, `review-python`, `review-powershell`, `review-javascript`, and `review-tsql` all
compose it now (2026-09-19; it was missing and this skill's first run tried to bolt it on as a
standalone role that does not exist — mixins are never rendered standalone, only woven into a full
recipe). It is where god classes, coupling and cohesion, composition over inheritance and implicit
conventions live — exactly the things Edward names every round. Nothing extra to append; read the
composed recipe body as normal.

Composed persona bodies live at `~/.personetta/claude-recipes/<recipe>.md`. Read the file and put
it in the dispatched agent's prompt. Do not paraphrase it, and do not run `personetta set-active` —
that switches Edward's own session persona, which is not what a dispatch needs.

If a recipe file is missing, say so and fall back to the closest one that exists rather than
inventing a persona inline.

## Per-repo configuration, optional

If the repo's `CLAUDE.md` or policy file has a `## Review board` section, it wins: it may name the
default persona set, per-persona model overrides, paths to always exclude, and the language recipes
to use for `developer` and `sdet`. **Absent, everything above applies unchanged** — the skill must
work in a repo that has never heard of it.

## Showing what a reviewer will ask for

Edward should never have to guess what a persona will do — with a pasted prompt he could read it,
and he must keep that. Three inspection modes, none of which dispatches anything:

- **`--show`** — per selected persona: the recipe id, the file it resolves to, the model and effort,
  the scope, and the persona's full **You Should** list, which is the substance of what it will look
  for. This is the default way to answer "what am I getting".
- **`--show-full`** — the entire composed persona body, verbatim, exactly as it would be sent. This
  is the pasted-prompt equivalent; it is a real file and it is readable.
- **`--where`** — just the paths, for when he wants to open or edit them himself.

The bodies live at `~/.personetta/claude-recipes/<recipe>.md` and are plain markdown — he can also
read them directly without this skill, which is the point of keeping the personas in Personetta.
If a body is missing from the cache, say that the recipes need installing rather than improvising.

Anything the skill adds on top of a persona — the output contract, the disposition ledger, the
cold-read context starvation — must also appear in `--show`, or the display is lying about what
gets sent.

## Where the ledger and findings live

Findings, `round.json`, and `dispositions.md` default to `docs/reviews/` **inside the target**, on
the assumption that the target is a git repo Edward will commit that history into. Check with
`git -C <target> rev-parse --is-inside-work-tree` (or equivalent) before assuming that.

**If the target is not a git repo**, `docs/reviews/` has no defined owner — writing it into an
arbitrary directory (a skills folder, a scratch checkout, someone else's tree) either pollutes it or
silently vanishes with no repo history to anchor it, and the "never re-raise settled ground"
guarantee evaporates exactly there. In that case use a location outside the target instead, keyed by
the target's absolute path so unrelated non-repo targets never collide:

```
~/.claude/skills/review/state/<slugified-target-path>/dispositions.md
~/.claude/skills/review/state/<slugified-target-path>/<date>/<persona>.md
~/.claude/skills/review/state/<slugified-target-path>/<date>/round.json
```

Slugify by replacing `:`, `\`, and `/` with `-` (e.g. `C:\Users\corio\.claude\skills\review` becomes
`C--Users-corio--claude-skills-review`). State which location is in effect — repo-relative or the
central store — in the same scope line as step 2 below, so Edward never has to guess where his
dispositions went.

## Pinning the target

A live-edited target broke this quietly on the first real run: the file under review grew by
roughly a hundred lines mid-board, and all three personas happened to cope. That was luck, not
design — nothing detected the drift or said so in the output.

1. **Pin a revision before dispatching the first persona.** If the target is a git repo, record the
   commit/ref (`git rev-parse HEAD`) and treat an unstaged working tree as part of the pin (note if
   it's dirty). If it is not a repo, snapshot a content hash per in-scope file (`sha256sum` or
   equivalent) at dispatch time. Every persona reviews that pinned snapshot's content.
2. **Before writing a persona's findings to disk, re-check the pin** — same ref, or same file
   hashes, whichever applies. If anything in scope changed since the pin:
   - Do not silently accept findings anchored to line numbers that may no longer be real.
   - Note the drift explicitly in that persona's findings file: what changed, by how much (line
     delta or which files), and whether the persona reviewed the old or new content.
   - If the drift is large enough that the persona's findings are likely stale (a file the persona
     covered grew or shrank by more than a trivial amount), re-run that persona against the current
     content rather than trust output verified against a version that no longer exists. If re-running
     is not affordable right now, say so and mark that persona's findings as provisional rather than
     final.
3. **Never let consolidation quietly merge findings pinned to different revisions.** If personas in
   the same round reviewed different snapshots, say so in `findings.md` before the ranked list, not
   as a footnote.

## Running a round

1. **Resolve the round.** Parse args. Resolve the ledger/findings location per the rule above. If an
   incomplete round exists there and `--restart` was not passed, resume it: skip personas already
   written.
2. **Establish scope** and state it in one line before dispatching: which paths, how many files,
   which personas, which models, sequential or parallel, and the resolved ledger location.
3. **Read the disposition ledger first** — `dispositions.md` at the resolved location, if present.
   Findings Edward has already declined, with his reason, are **not to be raised again**. This is the
   single most important thing this skill does; he has said the friction of re-litigating settled
   code smells is why review rounds wear him down.
4. **Dispatch one persona at a time** (his standing rule: *"go one at a time so that we minimize
   losses if there's a session break"*). Each agent gets: the composed persona body, the scope, the
   repo's own policy file, the disposition ledger, and the output contract below.
   - `coldread` is the exception: give it **no** design docs, no decision log, no prior findings,
     no CLAUDE.md. Its accuracy depends on reading cold. Say so in its prompt.
5. **Write findings to disk the moment a persona finishes** — `<date>/<persona>.md` at the resolved
   location — before dispatching the next. Update `round.json`. Then print one progress line:
   persona, findings that survived verification, elapsed, what is next.
6. **After the last persona**, run the consolidation pass: verify, dedup, rank, and write
   `<date>/findings.md` at the resolved location.
7. **End the round in chat, not in a file.** Print the foundational shortlist — one line per
   finding: what, `file:line`, smallest fix — then the counts (other findings, dropped in
   verification), then a clickable link to `findings.md`. He should never have to go looking for
   what the board found; the file is the full record, the chat is the answer.

## The output contract every persona must follow

Each finding carries:

- **What** — one sentence stating the defect, not the topic
- **Where** — `file:line`, or the set of locations for a systemic finding
- **Why it costs him** — in terms of maintaining this code later, not abstract principle
- **Evidence** — the census table, the call graph result, the measured rate, the failing input
- **Smallest fix** — the least change that removes the problem, not a redesign
- **Foundational or local** — foundational means other work depends on it being right, or it will
  get more expensive to fix the longer it waits. This is Edward's triage axis; he fixes foundational
  now and defers the rest
- **Severity** — blocker, warning, nit

And the standing checklist he repeats in every round: **DRY, SRP, SOLID, YAGNI, no magic constants,
small focused methods, no god classes, tests must always pass.**

## Verification — the anti-slop pass

Before any finding reaches him, it must survive an adversarial check: *what input, what state, what
actually breaks?* A finding that cannot be made concrete is dropped, not softened. Report how many
were dropped; that number is how he calibrates trust in the board.

For a systemic finding, the evidence is the census — every location, with lines. *"This looks
duplicated"* is not a finding. Two similar implementations are a watch item; three are a finding.

## Consolidation

- **Dedup across personas.** Four reviewers will find the same god class. Emit one finding with the
  corroborating views named — agreement is signal, repetition is noise.
- **Rank foundational first**, then by severity, then by cost to fix.
- **Cap the headline list.** If a round produces eighty findings, lead with the foundational ones
  and put the rest behind a count. His review of 2026-09-04 produced 57 rows and he remediated only
  the foundational ones; give him that shortlist directly, in chat (step 7).
- **Name what the board did not look at** — scope excluded, personas skipped, budget exhausted.

## Recording dispositions

When he says what to do with findings, record it in `dispositions.md` at the resolved location (see
"Where the ledger and findings live" above): the finding, the date, and **fixed / won't-fix /
deferred with his reason**. The next round reads this first.

Never mark a disposition on his behalf. A finding nobody has ruled on stays open.

## Rules

- **Never fix anything.** This skill reviews. Remediation is a separate instruction, and he wants to
  choose what gets remediated.
- Never file work items off an unreviewed round; he decides what becomes a task.
- Do not review a diff — that is `/code-review`. Coherence in particular is meaningless diff-scoped:
  diff review is exactly how systemic drift survives.
- Respect the repo's own policy file over this skill for anything project-specific.
- During unattended work, park questions rather than blocking, and never ask between 21:00 and 07:00.
- **The default persona set is all eight, because Edward asked for all eight.** He said so plainly
  when the skill was specified: default the full board, and give him a way to cancel a cycle. That
  instruction stands, and the cost measurement does not overturn it — he is not avoiding this board
  out of ignorance of what it costs, and quietly halving it would decide on his behalf.
- **State the cost before dispatching, every time.** A 3-persona round on this skill's own first
  live run cost 384,402 tokens and ~14 minutes sequential; eight extrapolates to roughly 900K-1.1M
  tokens and 35-45 minutes. Put the estimate for whatever set is selected in the same scope line as
  step 2 of "Running a round." Informing the choice is the job; making it for him is not. `--core`
  runs the four that carry the most weight (architect, developer, coherence, sdet: structure, code
  quality, systemic drift, testedness) when the round does not warrant the full board.
