#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the upstream-outcome ledger from GitHub, not from a hand-kept list.

The roadmap is written by the author of the skill. That makes it the wrong
place to read a merge rate from: a list you curate is a list you can curate
favourably, and a sweep of this account's real pull requests found seven the
roadmap had omitted -- two of them merges, three of them rejections.

So this reads GitHub instead. The inclusion rule is fixed and mechanical: any
pull request opened by the account, against a repository the account does not
own, whose body names the skill. Every such PR is reported with the outcome
GitHub reports, whether it flatters the project or not.

What this supports: "maintainers of these projects accepted or rejected these
specific changes, and you can open any one of them."

What it does not support: a precision figure for the reviewer. A merge means a
maintainer accepted a patch; it does not certify that the finding's severity
was classified correctly, and a rejection is often about scope, staleness, or
timing rather than the merits. The stated bias below is the one that matters
most and it is not correctable from here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


MARKERS = ("e2e-reviewer", "e2e-skills")


def gh_json(*args: str):
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise SystemExit(f"gh failed: {' '.join(args)}\n{result.stderr.strip()[:400]}")
    return json.loads(result.stdout or "[]")


def collect(account: str) -> list[dict]:
    found: dict[str, dict] = {}
    for marker in MARKERS:
        for pr in gh_json(
            "search", "prs", "--author", account, marker, "--limit", "200",
            "--json", "repository,number,state,title,url,createdAt",
        ):
            repo = pr["repository"]["nameWithOwner"]
            if repo.startswith(f"{account}/"):
                continue  # the project's own repository is not a field result
            found[pr["url"]] = {
                "repository": repo,
                "number": pr["number"],
                "state": pr["state"],
                "title": pr["title"],
                "url": pr["url"],
                "created_at": pr["createdAt"],
                "matched_marker": marker,
            }
    return sorted(found.values(), key=lambda p: (p["repository"], p["number"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="voidmatcha")
    parser.add_argument("--output", default="benchmarks/field-review-v1/ledger.json")
    args = parser.parse_args()

    entries = collect(args.account)
    states = Counter(e["state"] for e in entries)
    decided = states["merged"] + states["closed"]

    payload = {
        "schema_version": 1,
        "account": args.account,
        "inclusion_rule": (
            "Every pull request opened by the account against a repository it "
            "does not own, whose body names one of "
            f"{list(MARKERS)}. Outcomes are whatever GitHub reports."
        ),
        "known_undercount": (
            "The submission footer is optional, so a PR that carried no marker "
            "is invisible here. That makes the denominator a lower bound, and "
            "an unmarked rejection would bias the merge rate upward. The "
            "direction of this bias is known; its size is not."
        ),
        "not_supported": (
            "This is not a precision figure for the reviewer. A merge means a "
            "maintainer accepted a patch, not that the finding's severity was "
            "classified correctly; a rejection is often scope or timing."
        ),
        "totals": {
            "submitted": len(entries),
            "merged": states["merged"],
            "closed_without_merge": states["closed"],
            "open": states["open"],
            "decided": decided,
        },
        "repositories": len({e["repository"] for e in entries}),
        "pull_requests": entries,
    }
    Path(args.output).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    t = payload["totals"]
    print(
        f"{t['submitted']} submitted across {payload['repositories']} repositories: "
        f"{t['merged']} merged, {t['closed_without_merge']} closed, {t['open']} open "
        f"-> {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
