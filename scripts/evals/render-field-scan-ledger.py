#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Render the field-scan ledger as a readable Markdown page.

Reads only the JSON ledger; runs no scan and makes no model call. The point of
the page is that a skeptic can click any row and land on the exact line in the
upstream repository at the pinned commit.

Two things this renderer must never blur:

  * A `[LLM-TRIAGE]` hit is a *candidate*, not a defect. The deterministic
    scanner cannot decide those alone, so they are counted and displayed apart
    from the P0 hits and are never folded into a defect total.
  * A repository whose scan suppressed a rule is incomplete. Its counts are a
    floor, not a measurement, and the row says so.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def severity_bucket(hit: dict) -> str:
    if hit.get("triage"):
        return "triage"
    return "p0" if hit["severity"] == "P0" else "other"


def render(payload: dict) -> str:
    repositories = payload["repositories"]
    scanned = [r for r in repositories if r["status"] == "scanned"]
    incomplete = [r for r in scanned if r.get("incomplete")]

    lines: list[str] = []
    add = lines.append

    add("# Field scan v1 — ledger\n")
    add(
        "Every hit the deterministic scanner produced on the pinned public "
        "repositories, with nothing removed for how it looks. No model was "
        "called (`model_calls: 0`), no pull request was opened, and no upstream "
        "repository was modified. Each line below links to the exact line at "
        "the pinned commit, so any row can be checked without trusting this "
        "page.\n"
    )
    add("## How to read the counts\n")
    add(
        "- **P0** — the deterministic checks for silent always-pass shapes. "
        "These are the load-bearing hits.\n"
        "- **Triage candidates** — hits the scanner tags `[LLM-TRIAGE]`. The "
        "scanner cannot decide these on its own, so they are **candidates for "
        "review, not defects**, and are never added to a defect total.\n"
        "- **AST-origin** — Tier 2 hits counted in the scanner's own Summary "
        "but printed in a different shape, so they are reconciled here rather "
        "than re-listed.\n"
        "- **Incomplete** — a rule hit the bounded per-rule limit and was "
        "suppressed. That repository's counts are a floor, not a measurement.\n"
    )

    add("## Selection\n")
    add(
        "The selection rule was frozen and committed before this scan ran: "
        f"[`{payload['selection_rule']}`]"
        f"(../../{payload['selection_rule']}).\n"
    )
    add(
        f"Repositories excluded as contaminated (already used in development): "
        f"**{payload['excluded_contaminated_count']}**. "
        f"Scanned: **{len(scanned)}/{len(repositories)}**.\n"
    )

    add("## Per repository\n")
    add("| Repository | Commit | P0 | Triage candidates | Other | AST-origin | Complete |")
    add("|---|---|---:|---:|---:|---:|:--:|")
    totals = Counter()
    incomplete_repos = 0
    for entry in repositories:
        repo, sha = entry["repository"], entry["sha"]
        if entry["status"] != "scanned":
            add(f"| [{repo}](https://github.com/{repo}) | `{sha[:10]}` | — | — | — | — | "
                f"{entry['status']} |")
            continue
        buckets = Counter(severity_bucket(h) for h in entry["hits"])
        ast = entry.get("scanner_counts", {}).get("ast", 0)
        totals.update(buckets)
        totals["ast"] += ast
        partial = bool(entry.get("incomplete"))
        if partial:
            incomplete_repos += 1
        complete = "yes" if not partial else "**no**"

        # A suppressed rule reports nothing, so its zero is indistinguishable
        # from a genuine absence. Rendering a bare number here would let a
        # missing rule read as a clean repository, which is the exact failure
        # the INCOMPLETE label exists to prevent.
        def cell(value: int) -> str:
            return f"\u2265{value}" if partial else str(value)

        add(
            f"| [{repo}](https://github.com/{repo}) | "
            f"[`{sha[:10]}`](https://github.com/{repo}/tree/{sha}) | "
            f"{cell(buckets['p0'])} | {cell(buckets['triage'])} | "
            f"{cell(buckets['other'])} | {cell(ast)} | {complete} |"
        )
    floor = "\u2265" if incomplete_repos else ""
    add(
        f"| **Total** | | **{floor}{totals['p0']}** | **{floor}{totals['triage']}** | "
        f"**{floor}{totals['other']}** | **{floor}{totals['ast']}** | |"
    )
    add("")
    if incomplete_repos:
        add(
            f"\u2265 marks a floor, not a count: {incomplete_repos} of "
            f"{len(scanned)} scanned repositories had at least one rule "
            "suppressed at the bounded per-rule limit, and a suppressed rule "
            "reports nothing. **A zero in one of those rows does not mean the "
            "repository is clean** \u2014 it means the check did not finish. "
            "The bound was left at its shipped default rather than raised "
            "after seeing these results.\n"
        )

    if incomplete:
        add("### Incomplete scans\n")
        add(
            "A rule that exceeds the bounded per-rule limit suppresses itself "
            "and reports nothing; the rest of the scan still runs. The counts "
            "for these repositories are therefore a lower bound.\n"
        )
        for entry in incomplete:
            add(f"- **{entry['repository']}** — {len(entry['incomplete'])} rule(s) suppressed:")
            for detail in entry["incomplete"]:
                add(f"  - {detail}")
        add("")

    add("## P0 hits\n")
    add(
        "Deterministic P0 findings only. Triage candidates are listed "
        "separately below and are not defects.\n"
    )
    p0 = [h for r in scanned for h in r["hits"] if severity_bucket(h) == "p0"]
    if not p0:
        add(
            "_None listed._"
            + (
                " This is not a finding of cleanliness: P0 rules were among "
                "those suppressed in the incomplete scans above.\n"
                if incomplete
                else "\n"
            )
        )
    else:
        by_pattern = Counter(h["pattern_id"] for h in p0)
        add("| Pattern | Hits |")
        add("|---|---:|")
        for pattern, count in by_pattern.most_common():
            add(f"| `{pattern}` | {count} |")
        add("")
        add("| Pattern | Location |")
        add("|---|---|")
        for hit in sorted(p0, key=lambda h: (h["repository"], h["file"], h["line"])):
            add(
                f"| `{hit['pattern_id']}` | "
                f"[{hit['repository']}/{hit['file']}:{hit['line']}]({hit['permalink']}) |"
            )
        add("")

    triage = [h for r in scanned for h in r["hits"] if severity_bucket(h) == "triage"]
    add("## Triage candidates\n")
    add(
        "**These are not defects.** The scanner flags them as needing a "
        "judgement it cannot make deterministically. They are published so the "
        "P0 column above cannot be inflated by quietly counting them.\n"
    )
    if not triage:
        add("_None._\n")
    else:
        by_pattern = Counter(h["pattern_id"] for h in triage)
        add("| Pattern | Candidates |")
        add("|---|---:|")
        for pattern, count in by_pattern.most_common():
            add(f"| `{pattern}` | {count} |")
        add("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", default="benchmarks/field-scan-v1/ledger.json")
    parser.add_argument("--output", default="benchmarks/field-scan-v1/ledger.md")
    args = parser.parse_args()

    payload = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
    Path(args.output).write_text(render(payload), encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
