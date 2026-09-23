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

Inside Claude Code, type the skill's name or say what you want: `handoff kitchen-remodel`,
`pickup kitchen-remodel`, `checkpoint`, `magazine`, `diagram`, `publish this`. Each skill's
`SKILL.md` says when it applies.
