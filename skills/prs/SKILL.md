---
name: prs
description: List the pull requests waiting only on the user's vote, in the order they should merge, each with a link. Works on any repo whose origin is Azure DevOps or GitHub. Use when he says "prs", "my prs", "what PRs are ready", "what needs my vote", "what can I merge", or asks which PRs to approve and in what order.
---

# PRs

Edward votes from a list. This skill gives him that list: only the PRs that need nothing but his
vote, already in merge order, one line each with a link he can click.

## Run it

From the repo's main checkout (never from inside a live proof or artifacts folder):

```bash
python ~/.claude/skills/prs/scripts/ready_prs.py
```

`--me "<name>"` overrides who "you" are (default: `git config user.name` on Azure DevOps, the
`gh` login on GitHub). `--json` gives the raw rows. The script is read-only: it queries `az repos`
or `gh` and fetches branches; it never votes, comments or merges.

**Always run it live.** Never answer from an earlier list in the conversation: a PR he already
approved, or one that merged since, must not reappear.

## What counts as ready

Open, not a draft, merges cleanly, at least one approving vote from someone else (on Maestro that
is the Maestro Reviewer after the AI review converged), no rejecting vote, and no vote from him
yet. Anything short of that is not his to act on and does not appear.

## The order

First rule wins:

1. **Stacked PRs** merge after the PR they are built on.
2. **Work-item priority**: lower Priority first; at equal priority a bug before a story.
3. **No overlap first**: a PR touching files no other ready PR touches cannot be disturbed by the
   others' merges; overlapping ones go later and may need a re-stamp after the earlier merge.
4. **Smaller diff, then older PR.**

## Report

Print the list exactly as the script gives it: a numbered line per PR, the link on the PR number
and title, then the short reason for its place. Add nothing above it but a one-line count
(`6 PRs ready for your vote, in merge order:`). If two ready PRs overlap, add one line after the
list naming which later PR may need a re-stamp once the earlier one merges. If the list is empty,
say so in one line.

Do not start work off the back of this list; voting is his.
