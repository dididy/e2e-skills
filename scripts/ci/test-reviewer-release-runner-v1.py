#!/usr/bin/env python3
"""Focused tests for the reviewer-release-v1 preflight planner."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/evals/run-reviewer-release-v1.py"
PROTOCOL_PATH = ROOT / "scripts/evals/reviewer-release-v1-protocol.json"
SPEC = importlib.util.spec_from_file_location("reviewer_release_v1_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def invoke(*args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.stderr == "", completed.stderr
    lines = completed.stdout.splitlines()
    assert len(lines) == 1, completed.stdout
    return completed, json.loads(lines[0])


def main() -> None:
    protocol_result, protocol_payload = invoke("--protocol-only")
    assert protocol_result.returncode == 0
    assert protocol_payload["status"] == "PROTOCOL_VALID"
    assert protocol_payload["execution_plan"] is None

    protocol = RUNNER.load_json(PROTOCOL_PATH)
    plan = RUNNER.protocol_schedule(protocol)
    assert plan["arms"] == ["full", "catalog-only", "no-skill"]
    assert plan["independent_case_count"] == 120
    assert plan["repetitions_count_as_independent_cases"] is False
    assert plan["host_model_count"] == 1
    assert plan["cell_count"] == 3
    assert plan["planned_model_invocations"] == 1080
    assert [cell["planned_invocations"] for cell in plan["cells"]] == [360, 360, 360]

    missing_bundle, payload = invoke(
        "--attestation-verifier", sys.executable,
        "--runner-path", f"codex-gpt-5.6-sol={sys.executable}",
        "--dry-run",
    )
    assert missing_bundle.returncode == 2
    assert payload["status"] == "BLOCKED"
    assert "--bundle is required" in payload["error"]

    with tempfile.TemporaryDirectory(prefix="reviewer-release-runner-v1-") as raw:
        temp = Path(raw)
        bundle = temp / "bundle"
        bundle.mkdir()
        marker = temp / "model-was-called"
        model_runner = temp / "trusted-model-runner"
        model_runner.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n", encoding="utf-8")
        model_runner.chmod(0o755)
        original_validate = RUNNER.run_validator
        RUNNER.run_validator = lambda *_args, **_kwargs: {"mode": "release-ready", "status": "PASS"}
        try:
            args = argparse.Namespace(
                protocol=PROTOCOL_PATH,
                bundle=bundle,
                attestation_verifier=Path(sys.executable),
                runner_path=[f"codex-gpt-5.6-sol={model_runner}"],
                protocol_only=False,
                dry_run=True,
            )
            payload = RUNNER.execute(args)
        finally:
            RUNNER.run_validator = original_validate
        assert payload["status"] == "EXECUTION_PREREQUISITES_VALID"
        assert payload["next_action"] == "EXECUTOR_NOT_IMPLEMENTED"
        assert payload["model_execution_attempted"] is False
        assert not marker.exists(), "preflight planner invoked the model runner"

    no_primary = json.loads(json.dumps(protocol))
    no_primary["execution_identity"]["primary"] = {}
    try:
        RUNNER.protocol_schedule(no_primary)
    except RUNNER.ReleasePlanError as exc:
        assert "execution_identity.primary" in str(exc)
    else:
        raise AssertionError("missing primary identity must fail closed")

    unknown, payload = invoke("--not-a-real-flag")
    assert unknown.returncode == 2
    assert payload["status"] == "BLOCKED"
    assert "argument error" in payload["error"]

    print("reviewer release runner v1 tests: 8 passed")


if __name__ == "__main__":
    main()
