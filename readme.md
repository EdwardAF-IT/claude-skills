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
| `handoff` | Ends a session with a note the next one resumes from, without losing the thread. | `handoff kitchen-remodel` |
| `pickup` | Starts a session from that note, catches up on what changed since, and keeps going. | `pickup kitchen-remodel` |
| `checkpoint` | Saves a snapshot of where things stand and keeps working — for when you step away. | `checkpoint` |
| `sitrep` | A one-screen status report: what got done, what's running, what needs you. | `status?` |
| `asks` | Asks every question it has for you back to back, walks you through your own todos, then acts on the answers. | `my asks` |

### Documents

| Skill | What it does | Say |
|---|---|---|
| `diagram` | Adds or fixes diagrams in markdown, picking the right kind and keeping labels legible. | `diagram this` |
| `edit` | Tightens wordy writing without dropping a single fact. | `tighten this` |
| `magazine` | Turns markdown into a colorful, printable magazine-style edition. | `make this printable` |
| `publish` | Runs diagram → edit → magazine in one pass, from draft to reading copy. | `publish this` |

### Code and agents

| Skill | What it does | Say |
|---|---|---|
| `design` | Hands a hard question to a deeper-thinking model and writes the proposal into the repo. | `design the sync layer` |
| `review` | A review board of up to eight reviewer personas over a whole codebase, findings verified and ranked. | `review board` |
| `prs` | Lists the pull requests waiting only on your vote, in merge order, with links. | `prs` |
| `agent-budget` | Caps how many subagents run at once, weighted by model, so a session doesn't hit its limit. | `set the budget to 8` |
