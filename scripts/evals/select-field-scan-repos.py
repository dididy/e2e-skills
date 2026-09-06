#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the frozen field-scan selection rule and pin the sample.

The rule lives in benchmarks/field-scan-v1/README.md and was committed before
this ran. This script only executes it; it does not decide anything.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def gh_json(args: list[str]) -> object:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} failed: {result.stderr.strip()[:300]}")
    return json.loads(result.stdout or "[]")


def contaminated_repos() -> set[str]:
    """Repositories this project has ever opened a pull request against."""
    seen: set[str] = set()
    for page in range(1, 4):
        rows = gh_json([
            "search", "prs", "--author", "voidmatcha",
            "--limit", "100", "--json", "repository",
        ])
        for row in rows:
            seen.add(row["repository"]["nameWithOwner"])
        break  # gh search caps at 100; one page is what it will return
    return seen


def candidates(query: str, limit: int) -> list[str]:
    rows = gh_json([
        "search", "code", "--limit", str(limit), "--json", "repository", query
    ])
    ordered: list[str] = []
    for row in rows:
        name = row["repository"]["nameWithOwner"]
        if name not in ordered:
            ordered.append(name)
    return ordered


def repo_meta(name: str) -> dict | None:
    try:
        return gh_json([
            "api", f"repos/{name}",
            "--jq", "{full_name,stargazers_count,fork,archived,default_branch}",
        ])
    except SystemExit:
        return None


def head_sha(name: str, branch: str) -> str | None:
    try:
        data = gh_json(["api", f"repos/{name}/commits/{branch}", "--jq", "{sha}"])
        return data["sha"]
    except (SystemExit, KeyError, TypeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--take", type=int, default=12)
    parser.add_argument("--output", default="benchmarks/field-scan-v1/repos.json")
    args = parser.parse_args()

    excluded = contaminated_repos()
    print(f"excluded (author has opened a PR there): {len(excluded)} repositories")

    pool: list[str] = []
    for query in (
        '"@playwright/test" filename:package.json',
        '"cypress" filename:package.json',
    ):
        for name in candidates(query, 100):
            if name not in pool:
                pool.append(name)
    print(f"candidate pool: {len(pool)}")

    scored = []
    for name in pool:
        if name in excluded:
            continue
        meta = repo_meta(name)
        if not meta or meta.get("fork") or meta.get("archived"):
            continue
        scored.append((meta["stargazers_count"], name, meta["default_branch"]))

    # Rule step 2: stars descending, name ascending on ties.
    scored.sort(key=lambda row: (-row[0], row[1]))

    selected = []
    for stars, name, branch in scored:
        if len(selected) >= args.take:
            break
        sha = head_sha(name, branch)
        if not sha:
            continue
        selected.append({
            "repository": name,
            "stars": stars,
            "default_branch": branch,
            "sha": sha,
        })
        print(f"  {len(selected):2d}. {name} ({stars} stars) @ {sha[:10]}")

    payload = {
        "schema_version": 1,
        "selection_rule": "benchmarks/field-scan-v1/README.md",
        "excluded_contaminated_count": len(excluded),
        "candidate_pool_size": len(pool),
        "repositories": selected,
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"\npinned {len(selected)} repositories -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
