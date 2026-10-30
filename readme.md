# Claude Code skills

Custom skills for [Claude Code](https://claude.com/claude-code): handoff and pickup between
sessions, checkpoints, a design pass, a review board, and a document pipeline (diagram → edit →
magazine → publish) that turns a markdown design into a printable edition.

## Install

Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/EdwardAF-IT/claude-skills/main/install.ps1 | iex
```

Mac or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/EdwardAF-IT/claude-skills/main/install.sh | bash
```

It installs what is missing (git, Node, Python, Graphviz, Claude Code, mermaid-cli,
highlight.js) and puts the skills in `~/.claude/skills`. Run the same line again to update; its
last line names the version you now have (the `version` file here, tagged `v1.0.0` and up).
Nothing else under `~/.claude` is touched. First time: open a new window, run `claude`, sign in.

## Use

Inside Claude Code, type the skill's name or just say what you want. Each skill's `SKILL.md`
says when it applies.

### Sessions

| Skill | What it does | Say |
|---|---|---|
| `handoff` | Ends a session with a note the next one resumes from, without losing the thread.   Saves tokens by making it easy to have shorter sessions for long activities. | `/handoff kitchen-remodel` |
| `pickup` | Starts a session from that note, catches up on what changed since, and keeps going.  Saves tokens by making it easy to have shorter sessions for long activities.  | `/pickup kitchen-remodel` |
| `checkpoint` | Saves a snapshot of where things stand and keeps working — for when you step away. | `/checkpoint` |
| `sitrep` | A one-screen status report: what got done, what's running, what needs you. | `status?` or `/sitrep' |
| `asks` | Asks every question it has for you back to back, walks you through your own todos, then acts on the answers. | `my asks` or `/asks` |

### Documents

| Skill | What it does | Say |
|---|---|---|
| `diagram` | Adds or fixes diagrams that appear in markdown files, picking the right kind and keeping labels legible. | `/diagram this.md` |
| `edit` | Tightens wordy writing without dropping a single fact. | `tighten this` or `/edit that.md` |
| `magazine` | Turns markdown into a colorful, printable magazine-style edition. | `make this printable` or `/magazine that.md` |
| `publish` | Runs diagram → edit → magazine in one pass, from draft to reading copy. | `/publish this.md` |

### Code and agents

| Skill | What it does | Say |
|---|---|---|
| `design` | Hands a hard question to a deeper-thinking model and writes the proposal into the repo. | `design the sync layer` |
| `review` | A review board of up to eight reviewer personas over a whole codebase, findings verified and ranked. | `review board` |
| `prs` | Lists the pull requests waiting only on your vote, in merge order, with links. | `/prs` |
| `agent-budget` | Caps how many subagents run at once, weighted by model, so a session doesn't hit its limit.  It's a simple formula where haiku = 1, sonnet = 2, opus = 3, fable = 4, and thinking adds .5.  The agent can use any combination of agents with thinking on or off as it needs whose sum does not exceed your limit.  Encourages using economical models automatically for routine work.  I usually use an opus or sonnet w/thinking model as a coordinator who then spawns subagents when using this pattern.  | `set the budget to 8` or `/budget 12` |
