#!/usr/bin/env python3
"""List the pull requests waiting only on your vote, in the order they should merge.

Works on an Azure DevOps or GitHub remote (detected from `origin`). Read-only: it queries the
provider's CLI (`az repos` / `gh`) and fetches branches with git; it never votes, comments or merges.

A PR is "ready for you" when it is open, not a draft, merges cleanly, carries at least one approving
vote from someone else, carries no rejecting vote, and has no vote from you yet.

Merge order, first rule wins:
  1. A PR stacked on another ready PR merges after the one under it.
  2. Higher work-item priority first (Azure DevOps: the linked row's Priority; bugs before stories).
  3. A PR whose files no other ready PR touches before one that overlaps (it cannot be disturbed).
  4. Smaller diff first, then older PR first.

Usage: ready_prs.py [--me "Display Name or login"] [--json]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys


def run(args, check=True):
    """Runs a command and returns its stdout, or None when it fails and check is False."""
    # On Windows `az` is az.cmd, which CreateProcess cannot find by its bare name.
    exe = shutil.which(args[0]) or args[0]
    proc = subprocess.run([exe] + args[1:], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        if check:
            sys.exit("command failed: " + " ".join(args) + "\n" + proc.stderr.strip())
        return None
    return proc.stdout


def origin_url():
    """Returns origin's URL, or exits when the checkout has no origin."""
    url = run(["git", "remote", "get-url", "origin"], check=False)
    if not url:
        sys.exit("no 'origin' remote in this checkout")
    return url.strip()


def azure_prs(url, me):
    """Reads open PRs, votes and linked work items from Azure DevOps."""
    m = re.match(r"https://(?:[^@/]+@)?dev\.azure\.com/([^/]+)/([^/]+)/_git/([^/?#]+)", url)
    if not m:
        sys.exit("origin is not an Azure DevOps git URL: " + url)
    org, project, repo = m.groups()
    org_url = "https://dev.azure.com/" + org
    raw = json.loads(run(["az", "repos", "pr", "list", "--org", org_url, "--project", project,
                          "--repository", repo, "--status", "active", "--top", "200", "-o", "json"]))
    prs = []
    for pr in raw:
        votes = [(r.get("displayName", ""), r.get("uniqueName", ""), r.get("vote", 0))
                 for r in pr.get("reviewers", [])]
        mine = [v for n, u, v in votes if me.lower() in (n.lower(), u.lower())]
        others = [v for n, u, v in votes if me.lower() not in (n.lower(), u.lower())]
        prs.append({
            "id": pr["pullRequestId"],
            "title": pr["title"],
            "url": org_url + "/" + project + "/_git/" + repo + "/pullrequest/" + str(pr["pullRequestId"]),
            "source": pr["sourceRefName"].replace("refs/heads/", ""),
            "target": pr["targetRefName"].replace("refs/heads/", ""),
            "created": pr.get("creationDate", ""),
            "draft": pr.get("isDraft", False),
            "clean": pr.get("mergeStatus") == "succeeded",
            "approved": any(v >= 5 for v in others),
            "rejected": any(v < 0 for n, u, v in votes),
            "my_vote_pending": not mine or all(v == 0 for v in mine),
            "priority": None,
            "kind": None,
        })
    for pr in prs:
        items = run(["az", "repos", "pr", "work-item", "list", "--id", str(pr["id"]), "--org", org_url,
                     "-o", "json"], check=False)
        for item in json.loads(items or "[]")[:1]:
            fields = item.get("fields", {})
            pr["priority"] = fields.get("Microsoft.VSTS.Common.Priority")
            pr["kind"] = fields.get("System.WorkItemType")
    return prs


def github_prs(me):
    """Reads open PRs and reviews from GitHub."""
    login = me or (run(["gh", "api", "user", "-q", ".login"]) or "").strip()
    raw = json.loads(run(["gh", "pr", "list", "--state", "open", "--limit", "200", "--json",
                          "number,title,url,isDraft,mergeable,headRefName,baseRefName,createdAt,reviews"]))
    prs = []
    for pr in raw:
        reviews = pr.get("reviews") or []
        mine = [r for r in reviews if (r.get("author") or {}).get("login", "").lower() == login.lower()]
        others = [r for r in reviews if r not in mine]
        prs.append({
            "id": pr["number"],
            "title": pr["title"],
            "url": pr["url"],
            "source": pr["headRefName"],
            "target": pr["baseRefName"],
            "created": pr.get("createdAt", ""),
            "draft": pr.get("isDraft", False),
            "clean": pr.get("mergeable") == "MERGEABLE",
            "approved": any(r.get("state") == "APPROVED" for r in others),
            "rejected": any(r.get("state") == "CHANGES_REQUESTED" for r in reviews),
            "my_vote_pending": not mine,
            "priority": None,
            "kind": None,
        })
    return prs


def changed_files(source, target):
    """Returns the files a branch changes against its target, from git."""
    run(["git", "fetch", "-q", "origin", source, target], check=False)
    out = run(["git", "diff", "--name-only", "origin/" + target + "...origin/" + source], check=False)
    return set((out or "").split())


def is_ancestor(a, b):
    """True when commit a is an ancestor of commit b."""
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], capture_output=True).returncode == 0


def order(ready):
    """Sorts ready PRs into merge order and records the reason for each position."""
    for pr in ready:
        pr["files"] = changed_files(pr["source"], pr["target"])
        pr["head"] = (run(["git", "rev-parse", "origin/" + pr["source"]], check=False) or "").strip()
    for pr in ready:
        others = [o for o in ready if o is not pr]
        pr["overlaps"] = sorted(o["id"] for o in others if pr["files"] & o["files"])
        pr["stacked_on"] = sorted(o["id"] for o in others
                                  if o["head"] and pr["head"] and o["head"] != pr["head"]
                                  and is_ancestor(o["head"], pr["head"])
                                  and not is_ancestor(o["head"], "origin/" + pr["target"]))

    def key(pr):
        priority = pr["priority"] if isinstance(pr["priority"], int) else 9
        bug_first = 0 if (pr["kind"] or "").lower() == "bug" else 1
        return (priority, bug_first, 1 if pr["overlaps"] else 0, len(pr["files"]), pr["created"])

    remaining = sorted(ready, key=key)
    placed, result = set(), []
    while remaining:
        nxt = next((p for p in remaining if set(p["stacked_on"]) <= placed), remaining[0])
        remaining.remove(nxt)
        placed.add(nxt["id"])
        result.append(nxt)
    for pr in result:
        reasons = []
        if pr["stacked_on"]:
            reasons.append("after !" + ", !".join(map(str, pr["stacked_on"])) + " (stacked)")
        if isinstance(pr["priority"], int):
            reasons.append("P" + str(pr["priority"]) + (" bug" if (pr["kind"] or "").lower() == "bug" else ""))
        reasons.append("touches files of !" + ", !".join(map(str, pr["overlaps"])) if pr["overlaps"]
                       else "no overlap with the others")
        reasons.append(str(len(pr["files"])) + " files")
        pr["why"] = "; ".join(reasons)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--me", help="your reviewer display name, unique name or login")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a numbered list")
    args = parser.parse_args()
    url = origin_url()
    if "dev.azure.com" in url or "visualstudio.com" in url:
        me = args.me or (run(["git", "config", "user.name"], check=False) or "").strip()
        prs = azure_prs(url, me)
    elif "github.com" in url:
        prs = github_prs(args.me)
    else:
        sys.exit("origin is neither Azure DevOps nor GitHub: " + url)
    ready = [p for p in prs if not p["draft"] and p["clean"] and p["approved"]
             and not p["rejected"] and p["my_vote_pending"]]
    ordered = order(ready)
    if args.json:
        print(json.dumps([{k: v for k, v in p.items() if k not in ("files", "head")} for p in ordered], indent=2))
        return
    if not ordered:
        print("No PRs are waiting on your vote.")
        return
    for n, pr in enumerate(ordered, 1):
        print(str(n) + ". [!" + str(pr["id"]) + " " + pr["title"] + "](" + pr["url"] + ") - " + pr["why"])


if __name__ == "__main__":
    main()
