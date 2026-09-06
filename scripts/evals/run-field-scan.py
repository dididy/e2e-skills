#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the deterministic scanner over pinned public repositories.

Makes no model calls, opens no pull requests, and writes only to --output.
Every hit is recorded; nothing is filtered for how it looks.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "skills/e2e-reviewer/scripts/scan.sh"

HIT_RE = re.compile(r"^\s+(?P<path>/[^:]+):(?P<line>\d+):(?P<code>.*)$")
HEADER_RE = re.compile(r"^\[(?P<sev>P\d\??)\](?:\[(?P<tag>[A-Z-]+)\])?\s+(?P<id>#\S+)\s+(?P<title>.+?)\s+\(\d+ hits?\)$")
SUMMARY_RE = re.compile(
    r"^Summary(?P<incomplete_label> \[INCOMPLETE[^\]]*\])?: "
    r"(?P<total>\d+) total hit\(s\), (?P<p0>\d+) P0, "
    r"(?P<p1>\d+) P1/P2 heuristic, (?P<triage>\d+) LLM-triage, "
    r"(?P<candidate>\d+) P0 candidate; (?P<ast>\d+) AST-origin"
)
INCOMPLETE_RE = re.compile(r"^INCOMPLETE: (?P<detail>.+)$")


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 600):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
    )


def fetch(repo: str, sha: str, dest: Path) -> str | None:
    """Blobless partial clone pinned to one commit. Returns an error string."""
    url = f"https://github.com/{repo}.git"
    init = run(["git", "init", "--quiet", str(dest)])
    if init.returncode != 0:
        return f"git init failed: {init.stderr.strip()[:120]}"
    for cmd in (
        ["git", "remote", "add", "origin", url],
        ["git", "fetch", "--quiet", "--depth", "1", "--filter=blob:none", "origin", sha],
        ["git", "checkout", "--quiet", "FETCH_HEAD"],
    ):
        result = run(cmd, cwd=dest, timeout=900)
        if result.returncode != 0:
            return f"{' '.join(cmd[:2])} failed: {result.stderr.strip()[:160]}"
    return None


def parse_scan(stdout: str, stderr: str, root: Path, repo: str, sha: str):
    """Return (hits, scanner_counts, incomplete).

    The scanner's own Summary counts are recorded next to the parsed hits so a
    discrepancy is visible in the ledger instead of silently under-reporting.
    Tier 2 (AST) hits are counted in the Summary but printed in a different
    shape, which is the known reason the two numbers can differ.
    """
    hits: list[dict] = []
    current: dict | None = None
    counts: dict[str, int] = {}
    incomplete: list[str] = []
    for line in (stdout + "\n" + stderr).splitlines():
        broken = INCOMPLETE_RE.match(line)
        if broken:
            incomplete.append(broken.group("detail")[:200])
            continue
        header = HEADER_RE.match(line)
        if header:
            current = header.groupdict()
            continue
        summary = SUMMARY_RE.match(line)
        if summary:
            fields = summary.groupdict()
            counts = {
                "summary_incomplete": bool(fields.pop("incomplete_label")),
                **{k: int(v) for k, v in fields.items()},
            }
            current = None
            continue
        hit = HIT_RE.match(line)
        if hit and current:
            try:
                relative = Path(hit.group("path")).relative_to(root).as_posix()
            except ValueError:
                continue
            hits.append({
                "repository": repo,
                "sha": sha,
                "file": relative,
                "line": int(hit.group("line")),
                "pattern_id": current["id"],
                "severity": current["sev"],
                "triage": current["tag"] or None,
                "title": current["title"],
                "permalink": f"https://github.com/{repo}/blob/{sha}/{relative}#L{hit.group('line')}",
            })
    return hits, counts, incomplete


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repos", default="benchmarks/field-scan-v1/repos.json")
    parser.add_argument("--output", default="benchmarks/field-scan-v1/ledger.json")
    parser.add_argument("--limit", type=int, default=0, help="scan only the first N")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reuse repositories already scanned at the same pinned commit in --output",
    )
    args = parser.parse_args()

    spec = json.loads(Path(args.repos).read_text(encoding="utf-8"))
    repositories = spec["repositories"]
    if args.limit:
        repositories = repositories[: args.limit]

    output = Path(args.output)

    def write_ledger(results: list) -> None:
        payload = {
            "schema_version": 1,
            "selection_rule": spec["selection_rule"],
            "excluded_contaminated_count": spec["excluded_contaminated_count"],
            "model_calls": 0,
            "repositories": results,
        }
        # Written after every repository. A twelve-repository run is long enough
        # that an interrupted process must not discard the repositories that
        # already completed: an earlier run was killed on the fourth repository
        # and lost all three finished scans.
        tmp_out = output.with_suffix(output.suffix + ".partial")
        tmp_out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        tmp_out.replace(output)

    # Resume: a repository already recorded at the same pinned commit is not
    # rescanned. Keyed on (repository, sha) so a re-pinned commit still reruns.
    done: dict[tuple[str, str], dict] = {}
    if args.resume and output.exists():
        for entry in json.loads(output.read_text(encoding="utf-8"))["repositories"]:
            if entry.get("status") == "scanned":
                done[(entry["repository"], entry["sha"])] = entry

    results = []
    for index, entry in enumerate(repositories, 1):
        repo, sha = entry["repository"], entry["sha"]
        cached = done.get((repo, sha))
        if cached is not None:
            print(f"[{index}/{len(repositories)}] {repo} @ {sha[:10]} — already scanned",
                  flush=True)
            results.append(cached)
            write_ledger(results)
            continue
        print(f"[{index}/{len(repositories)}] {repo} @ {sha[:10]}", flush=True)
        tmp = Path(tempfile.mkdtemp(prefix="field-scan-"))
        try:
            error = fetch(repo, sha, tmp)
            if error:
                print(f"    skipped: {error}")
                results.append({**entry, "status": "fetch-failed",
                                "error": error, "hits": []})
                write_ledger(results)
                continue
            scan = run(["/bin/bash", "-p", str(SCAN), str(tmp)], timeout=1800)
            hits, counts, incomplete = parse_scan(
                scan.stdout, scan.stderr, tmp.resolve(), repo, sha
            )
            reported = counts.get("total", 0)
            ast = counts.get("ast", 0)
            unexplained = reported - len(hits) - ast
            print(f"    exit={scan.returncode} summary_total={reported} "
                  f"listed={len(hits)} ast={ast} unexplained={unexplained} "
                  f"incomplete_rules={len(incomplete)}")
            results.append({
                **entry,
                "status": "scanned",
                "exit_code": scan.returncode,
                "scanner_counts": counts,
                "listed_hits": len(hits),
                "unexplained_delta": unexplained,
                "incomplete": incomplete,
                "hits": hits,
            })
        except subprocess.TimeoutExpired:
            print("    skipped: timeout")
            results.append({**entry, "status": "timeout", "hits": []})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            write_ledger(results)

    write_ledger(results)
    scanned = [r for r in results if r["status"] == "scanned"]
    print(f"\nscanned {len(scanned)}/{len(results)}; "
          f"{sum(len(r['hits']) for r in scanned)} hits -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
