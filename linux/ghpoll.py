#!/usr/bin/env python3
"""
ghpoll.py — glanceable git + GitHub state for the pet (and termbg).

Run backgrounded + throttled by the zsh precmd hook (linux/hooks.zsh) with
the current directory as argv[1]. Writes github.state.json:

    {"dirty": <int>, "pr_comments": <int>, "pr_open": <int>,
     "repo": "owner/name", "ts": <unix>}

`dirty`       — uncommitted files (git status --porcelain)
`pr_open`     — your open PRs in this repo
`pr_comments` — total comments (conversation + inline review) across them;
                the pet perks up with a "✉!" when this number climbs.

Everything is best-effort: if git or gh is missing, unauthenticated, or the
directory isn't a GitHub repo, we still write a valid file (dirty at least),
so consumers never choke. gh calls are capped so a poll stays cheap.
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STATE = os.path.join(ROOT, "github.state.json")
MAX_PRS = 8  # keep a poll cheap even with many open PRs


def run(args, cwd, timeout=8):
    try:
        r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def load_prev():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def git_dirty(cwd):
    out = run(["git", "status", "--porcelain", "-uno"], cwd)
    return len([ln for ln in out.splitlines() if ln.strip()])


def gh_repo(cwd):
    out = run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], cwd)
    return out.strip()


def gh_pr_comments(cwd):
    """(open_pr_count, total_comment_count) for the current user's PRs."""
    out = run(["gh", "pr", "list", "--author", "@me", "--state", "open",
               "--json", "number", "-q", ".[].number"], cwd)
    numbers = [n for n in out.split() if n.isdigit()][:MAX_PRS]
    total = 0
    for n in numbers:
        conv = run(["gh", "api", f"repos/{{owner}}/{{repo}}/issues/{n}/comments",
                    "-q", "length"], cwd)
        review = run(["gh", "api", f"repos/{{owner}}/{{repo}}/pulls/{n}/comments",
                      "-q", "length"], cwd)
        total += int(conv.strip() or 0) + int(review.strip() or 0)
    return len(numbers), total


def main():
    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    if not os.path.isdir(cwd):
        cwd = os.getcwd()
    prev = load_prev()
    state = {"dirty": git_dirty(cwd), "ts": int(time.time())}

    repo = gh_repo(cwd)
    if repo:
        state["repo"] = repo
        pr_open, pr_comments = gh_pr_comments(cwd)
        state["pr_open"] = pr_open
        state["pr_comments"] = pr_comments
    else:
        # carry forward the last known PR figures so a non-repo cd doesn't
        # look like "all your comments vanished" and falsely re-trigger later
        state["repo"] = prev.get("repo", "")
        state["pr_open"] = prev.get("pr_open", 0)
        state["pr_comments"] = prev.get("pr_comments", 0)

    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, STATE)


if __name__ == "__main__":
    main()
