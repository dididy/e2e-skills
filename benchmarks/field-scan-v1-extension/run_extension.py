#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Completion extension for the two field-scan-v1 rows that recorded
status=timeout under the former 1800s scan cutoff (ever-co/ever-gauzy,
open-mercato/open-mercato).

Differences from scripts/evals/run-field-scan.py, per the preregistered
extension protocol:

- No wall-clock timeout on the scanner subprocess itself. Duration is
  recorded as evidence, never used to abort a healthy run.
- A liveness loop samples the *entire* scanner process tree (not just the
  top PID — scan.sh's scope-worker/scope-source helpers run as their own
  process groups) every LIVENESS_INTERVAL_S: summed CPU time across all
  descendants, plus stdout/stderr byte growth. DEADLOCK_SAMPLES consecutive
  samples where neither signal increases by more than a small threshold vs.
  the previous sample is treated as a real deadlock (comparing against the
  previous sample rather than a running maximum means a short-lived child
  exiting between samples can register as one non-increasing sample, so a
  burst of very short-lived subprocesses near DEADLOCK_SAMPLES in a row
  could in principle trip this on a healthy run; it did not happen in any
  recorded attempt) — the tree is terminated and the row is recorded as
  status=deadlock-detected with the liveness samples as evidence. This is
  not a duration cutoff: a run that is genuinely producing output or
  burning CPU is never aborted regardless of elapsed time.
  This detector replaced an earlier top-PID-only sampler after one
  open-mercato attempt was stopped manually on live process-tree inspection
  (not the top-PID-only liveness.log, which alone was not diagnostic — see
  benchmarks/field-scan-v1-extension/README.md's "Note on attempt 2") and
  did not reproduce on a later identical-code retry.
- Pre/post source fingerprints (sha256 of `git ls-tree -r HEAD`) prove the
  checkout was not mutated by the scan. A scanner digest (sha256 of
  scan.sh) and sha256 hashes of captured stdout/stderr are recorded
  alongside the parsed hits so the run is independently reproducible.
- Completion requires exit 0 or 1, a single parsed Summary line, and a
  reconciled hit count (scanner_counts.total == listed_hits + ast_hits).
  Anything else is recorded as status=incomplete-evidence with the reason,
  never silently coerced into zero findings.

Makes no model calls, opens no pull requests, and mutates no third-party
repository. Never touches benchmarks/field-scan-v1/ledger.json.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN = ROOT / "skills/e2e-reviewer/scripts/scan.sh"
EXT_DIR = ROOT / "benchmarks/field-scan-v1-extension"
REPOS_JSON = EXT_DIR / "repos.json"
OUTPUT = EXT_DIR / "ledger.json"
LIVENESS_LOG = EXT_DIR / "liveness.log"
LIVENESS_INTERVAL_S = 120
DEADLOCK_SAMPLES = 6  # 6 * 120s = 12 minutes of zero CPU and zero output growth

HIT_RE = re.compile(r"^\s+(?P<path>/[^:]+):(?P<line>\d+):(?P<code>.*)$")
HEADER_RE = re.compile(r"^\[(?P<sev>P\d\??)\](?:\[(?P<tag>[A-Z-]+)\])?\s+(?P<id>#\S+)\s+(?P<title>.+?)\s+\(\d+ hits?\)$")
SUMMARY_RE = re.compile(
    r"^Summary(?P<incomplete_label> \[INCOMPLETE[^\]]*\])?: "
    r"(?P<total>\d+) total hit\(s\), (?P<p0>\d+) P0, "
    r"(?P<p1>\d+) P1/P2 heuristic, (?P<triage>\d+) LLM-triage, "
    r"(?P<candidate>\d+) P0 candidate; (?P<ast>\d+) AST-origin"
)
INCOMPLETE_RE = re.compile(r"^INCOMPLETE: (?P<detail>.+)$")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="surrogateescape")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], cwd: Path | None = None, timeout: int | None = 600):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout
    )


def fetch(repo: str, sha: str, dest: Path) -> str | None:
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


def tree_fingerprint(dest: Path) -> str:
    result = run(["git", "ls-tree", "-r", "HEAD"], cwd=dest, timeout=300)
    return sha256_text(result.stdout)


def parse_scan(stdout: str, stderr: str, root: Path, repo: str, sha: str):
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


def descendants(pid: int) -> list[int]:
    """All live descendant PIDs of pid, BFS order, pid itself excluded."""
    frontier = [pid]
    found: list[int] = []
    while frontier:
        parent = frontier.pop()
        children = run(["pgrep", "-P", str(parent)], timeout=10)
        if children.returncode != 0:
            continue
        for line in children.stdout.split():
            child = int(line)
            found.append(child)
            frontier.append(child)
    return found


def tree_cpu_seconds(pid: int) -> float:
    """Sum of cumulative CPU time (TIME field) across pid and all descendants."""
    pids = [pid] + descendants(pid)
    sample = run(["ps", "-o", "time=", "-p", ",".join(str(p) for p in pids)], timeout=15)
    total = 0.0
    for line in sample.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        try:
            if len(parts) == 3:
                h, m, s = parts
                total += int(h) * 3600 + int(m) * 60 + float(s)
            elif len(parts) == 2:
                m, s = parts
                total += int(m) * 60 + float(s)
        except ValueError:
            continue
    return total


def kill_tree(pid: int) -> None:
    pids = descendants(pid) + [pid]
    for p in pids:
        try:
            os.kill(p, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(3)
    for p in pids:
        try:
            os.kill(p, signal.SIGKILL)
        except ProcessLookupError:
            pass


def scan_no_timeout(target: Path, repo: str) -> tuple[int, str, str, float, bool]:
    """Returns (returncode, stdout, stderr, duration_s, deadlock_detected)."""
    start = time.monotonic()
    stdout_path = EXT_DIR / f".scan-stdout-{repo.replace('/', '_')}.tmp"
    stderr_path = EXT_DIR / f".scan-stderr-{repo.replace('/', '_')}.tmp"
    with stdout_path.open("wb") as out_fh, stderr_path.open("wb") as err_fh:
        proc = subprocess.Popen(
            ["/bin/bash", "-p", str(SCAN), str(target)],
            cwd=None, stdout=out_fh, stderr=err_fh,
        )
        deadlock = False
        stall_streak = 0
        last_cpu = 0.0
        last_bytes = 0
        with LIVENESS_LOG.open("a", encoding="utf-8") as live_fh:
            while proc.poll() is None:
                time.sleep(LIVENESS_INTERVAL_S)
                if proc.poll() is not None:
                    break
                cpu = tree_cpu_seconds(proc.pid)
                out_bytes = stdout_path.stat().st_size + stderr_path.stat().st_size
                cpu_moved = cpu > last_cpu + 0.5
                output_grew = out_bytes > last_bytes
                stall_streak = 0 if (cpu_moved or output_grew) else stall_streak + 1
                live_fh.write(json.dumps({
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "repository": repo,
                    "pid": proc.pid,
                    "tree_cpu_seconds": round(cpu, 1),
                    "output_bytes": out_bytes,
                    "stall_streak": stall_streak,
                }) + "\n")
                live_fh.flush()
                last_cpu, last_bytes = cpu, out_bytes
                if stall_streak >= DEADLOCK_SAMPLES:
                    live_fh.write(json.dumps({
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "repository": repo,
                        "event": "deadlock-detected",
                        "detail": f"{DEADLOCK_SAMPLES} consecutive samples "
                                  f"({DEADLOCK_SAMPLES * LIVENESS_INTERVAL_S}s) with no CPU "
                                  f"or output movement",
                    }) + "\n")
                    live_fh.flush()
                    kill_tree(proc.pid)
                    deadlock = True
                    break
        returncode = proc.wait()
    duration = time.monotonic() - start
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    stdout_path.unlink(missing_ok=True)
    stderr_path.unlink(missing_ok=True)
    return returncode, stdout, stderr, duration, deadlock


def main() -> int:
    spec = json.loads(REPOS_JSON.read_text(encoding="utf-8"))
    scanner_digest = sha256_file(SCAN)

    results: list[dict] = []
    if OUTPUT.exists():
        try:
            prior = json.loads(OUTPUT.read_text(encoding="utf-8"))
            results = [r for r in prior.get("repositories", []) if r.get("status") == "scanned"]
        except json.JSONDecodeError:
            results = []
    done = {(r["repository"], r["sha"]) for r in results}

    def write_ledger() -> None:
        payload = {
            "schema_version": 1,
            "extension_of": "benchmarks/field-scan-v1/ledger.json",
            "protocol": "benchmarks/field-scan-v1-extension/README.md",
            "scanner_digest_sha256": scanner_digest,
            "model_calls": 0,
            "repositories": results,
        }
        tmp_out = OUTPUT.with_suffix(OUTPUT.suffix + ".partial")
        tmp_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp_out.replace(OUTPUT)

    for index, entry in enumerate(spec["repositories"], 1):
        repo, sha = entry["repository"], entry["sha"]
        if (repo, sha) in done:
            print(f"[{index}] {repo} @ {sha[:10]} — already scanned in this extension ledger", flush=True)
            continue
        print(f"[{index}] {repo} @ {sha[:10]} — fetching", flush=True)
        tmp = Path(tempfile.mkdtemp(prefix="field-scan-ext-"))
        try:
            error = fetch(repo, sha, tmp)
            if error:
                print(f"    fetch failed: {error}", flush=True)
                results.append({**entry, "status": "fetch-failed", "error": error, "hits": []})
                write_ledger()
                continue

            pre_fp = tree_fingerprint(tmp)
            print(f"    fetched; source_fingerprint_pre={pre_fp[:16]}…; scanning (no wall-clock cutoff)", flush=True)

            returncode, stdout, stderr, duration, deadlock = scan_no_timeout(tmp, repo)
            post_fp = tree_fingerprint(tmp)
            hits, counts, incomplete = parse_scan(stdout, stderr, tmp.resolve(), repo, sha)

            reported = counts.get("total", 0)
            ast = counts.get("ast", 0)
            unexplained = reported - len(hits) - ast
            summary_lines = sum(1 for ln in (stdout + "\n" + stderr).splitlines() if SUMMARY_RE.match(ln))

            reasons = []
            if deadlock:
                reasons.append(f"deadlock: {DEADLOCK_SAMPLES * LIVENESS_INTERVAL_S}s with no "
                                f"CPU/output movement, tree terminated (see liveness.log)")
            if returncode not in (0, 1):
                reasons.append(f"exit_code={returncode}")
            if summary_lines != 1:
                reasons.append(f"summary_lines={summary_lines}")
            if incomplete:
                reasons.append(f"incomplete_rules={len(incomplete)}")
            if unexplained != 0:
                reasons.append(f"unexplained_delta={unexplained}")
            if pre_fp != post_fp:
                reasons.append("source_fingerprint_changed")

            evidence_ok = not deadlock and not reasons
            status = "deadlock-detected" if deadlock else ("scanned" if evidence_ok else "incomplete-evidence")

            print(f"    exit={returncode} duration_s={duration:.1f} summary_total={reported} "
                  f"listed={len(hits)} ast={ast} unexplained={unexplained} "
                  f"incomplete_rules={len(incomplete)} status={status}"
                  + (f" reasons={';'.join(reasons)}" if reasons else ""), flush=True)

            results.append({
                **entry,
                "status": status,
                "reasons": reasons,
                "exit_code": returncode,
                "duration_s": round(duration, 1),
                "scanner_counts": counts,
                "listed_hits": len(hits),
                "unexplained_delta": unexplained,
                "incomplete": incomplete,
                "source_fingerprint_pre_sha256": pre_fp,
                "source_fingerprint_post_sha256": post_fp,
                "stdout_sha256": sha256_text(stdout),
                "stderr_sha256": sha256_text(stderr),
                "hits": hits,
            })
        except Exception as exc:  # noqa: BLE001 - recorded as evidence, never silently swallowed
            print(f"    execution failure: {exc!r}", flush=True)
            results.append({**entry, "status": "execution-failed", "error": repr(exc), "hits": []})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            write_ledger()

    write_ledger()
    scanned = [r for r in results if r["status"] == "scanned"]
    print(f"\nscanned {len(scanned)}/{len(results)} to complete evidence -> "
          f"{OUTPUT.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
