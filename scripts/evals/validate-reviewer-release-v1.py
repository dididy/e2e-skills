#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed preflight for the reviewer release-v1 benchmark."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "scripts" / "ci" / "lib"
sys.path.insert(0, str(LIB))

from reviewer_taxonomy_contract import REVIEWER_TAXONOMY  # noqa: E402
from strict_json import (  # noqa: E402
    StrictJsonError,
    load_strict,
    require_exact_keys,
)


DEFAULT_PROTOCOL = ROOT / "scripts" / "evals" / "reviewer-release-v1-protocol.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PROTOCOL_KEYS = {
    "schema_version",
    "protocol_id",
    "status",
    "result",
    "decision_state",
    "claim_scope",
    "corpus",
    "arms",
    "pairing",
    "execution_identity",
    "schedule",
    "adjudication",
    "user_helpfulness",
    "statistics",
    "decision",
    "release_evidence",
    "current_evidence",
}
TAXONOMY = {pattern_id: severity for pattern_id, _title, severity in REVIEWER_TAXONOMY}


class ValidationError(ValueError):
    """Raised when release evidence is incomplete, ambiguous, or inconsistent."""


def fail(message: str) -> None:
    raise ValidationError(message)


def exact(value: Any, keys: set[str], context: str) -> dict[str, Any]:
    try:
        return require_exact_keys(value, keys, context=context)
    except StrictJsonError as exc:
        raise ValidationError(str(exc)) from exc


def expect(value: Any, expected: Any, context: str) -> None:
    if value != expected:
        fail(f"{context}: expected {expected!r}, got {value!r}")


def positive_int(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        fail(f"{context}: expected a positive integer")
    return value


def valid_sha256(value: Any, context: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        fail(f"{context}: expected a lowercase SHA-256 digest")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        fail(f"{path}: cannot hash file: {exc}")
    return digest.hexdigest()


def resolve_bundle_path(bundle: Path, value: Any, context: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        fail(f"{context}: expected a non-empty bundle-relative path")
    candidate = (bundle / value).resolve()
    try:
        candidate.relative_to(bundle.resolve())
    except ValueError:
        fail(f"{context}: path escapes the external bundle")
    if not candidate.is_file():
        fail(f"{context}: file does not exist: {value}")
    return candidate


def load_json(path: Path) -> Any:
    try:
        return load_strict(path, max_bytes=16_777_216)
    except StrictJsonError as exc:
        raise ValidationError(str(exc)) from exc


def validate_protocol(protocol: Any) -> None:
    protocol = exact(protocol, PROTOCOL_KEYS, "protocol")
    expect(protocol["schema_version"], 1, "protocol.schema_version")
    expect(protocol["protocol_id"], "reviewer-release-v1", "protocol.protocol_id")
    if protocol["status"] not in {"NOT_RUN", "FROZEN", "COMPLETE"}:
        fail("protocol.status: expected NOT_RUN, FROZEN, or COMPLETE")
    if protocol["result"] not in {"INCONCLUSIVE", "PASS", "FAIL"}:
        fail("protocol.result: expected INCONCLUSIVE, PASS, or FAIL")
    if not isinstance(protocol["decision_state"], str) or not protocol["decision_state"]:
        fail("protocol.decision_state: expected a non-empty string")

    claim_scope = exact(protocol["claim_scope"], {"measures", "excludes"}, "protocol.claim_scope")
    expect(
        set(claim_scope["measures"]),
        {"finding_accuracy", "same_host_skill_lift", "user_helpfulness"},
        "protocol.claim_scope.measures",
    )
    if not isinstance(claim_scope["excludes"], list) or not claim_scope["excludes"]:
        fail("protocol.claim_scope.excludes: expected explicit non-claims")

    corpus = exact(
        protocol["corpus"],
        {
            "custody", "unique_cases", "frameworks", "label_totals",
            "primary_findings_per_positive_case", "coverage", "deduplication_unit",
            "blinding", "reuse_forbidden",
        },
        "protocol.corpus",
    )
    expect(corpus["custody"], "external_sealed", "protocol.corpus.custody")
    expect(corpus["unique_cases"], 120, "protocol.corpus.unique_cases")
    frameworks = exact(corpus["frameworks"], {"playwright", "cypress"}, "protocol.corpus.frameworks")
    for framework in ("playwright", "cypress"):
        expect(
            exact(frameworks[framework], {"positive", "clean"}, f"protocol.corpus.frameworks.{framework}"),
            {"positive": 30, "clean": 30},
            f"protocol.corpus.frameworks.{framework}",
        )
    expect(
        exact(corpus["label_totals"], {"positive", "clean"}, "protocol.corpus.label_totals"),
        {"positive": 60, "clean": 60},
        "protocol.corpus.label_totals",
    )
    expect(corpus["primary_findings_per_positive_case"], 1, "protocol.corpus.primary_findings_per_positive_case")
    coverage = exact(
        corpus["coverage"],
        {
            "stable_pattern_count", "positive_opportunities_per_pattern_min",
            "distinct_clean_or_near_miss_guard_opportunities_per_pattern_min",
            "positive_cases_per_severity_stratum_min", "severity_strata",
            "cases_per_source_repository_max", "coverage_opportunities_are_additional_scoring_labels",
        },
        "protocol.corpus.coverage",
    )
    expect(coverage["stable_pattern_count"], len(TAXONOMY), "protocol.corpus.coverage.stable_pattern_count")
    expect(coverage["positive_opportunities_per_pattern_min"], 2, "protocol.corpus.coverage.positive_opportunities_per_pattern_min")
    expect(coverage["distinct_clean_or_near_miss_guard_opportunities_per_pattern_min"], 2, "protocol.corpus.coverage.distinct_clean_or_near_miss_guard_opportunities_per_pattern_min")
    expect(coverage["positive_cases_per_severity_stratum_min"], 10, "protocol.corpus.coverage.positive_cases_per_severity_stratum_min")
    expect(coverage["severity_strata"], ["P0", "P1", "P2"], "protocol.corpus.coverage.severity_strata")
    expect(coverage["cases_per_source_repository_max"], 2, "protocol.corpus.coverage.cases_per_source_repository_max")
    expect(coverage["coverage_opportunities_are_additional_scoring_labels"], False, "protocol.corpus.coverage.coverage_opportunities_are_additional_scoring_labels")
    if not isinstance(corpus["deduplication_unit"], str) or not corpus["deduplication_unit"]:
        fail("protocol.corpus.deduplication_unit: expected a non-empty unit")
    if not isinstance(corpus["blinding"], list) or not corpus["blinding"]:
        fail("protocol.corpus.blinding: expected blinding fields")
    if not isinstance(corpus["reuse_forbidden"], list) or not corpus["reuse_forbidden"]:
        fail("protocol.corpus.reuse_forbidden: expected forbidden prior corpora")

    arms = protocol["arms"]
    if not isinstance(arms, list) or len(arms) != 3:
        fail("protocol.arms: expected exactly three arms")
    arm_ids: set[str] = set()
    for index, raw in enumerate(arms):
        arm = exact(raw, {"id", "input"}, f"protocol.arms[{index}]")
        if not isinstance(arm["input"], str) or not arm["input"]:
            fail(f"protocol.arms[{index}].input: expected a non-empty frozen input")
        arm_ids.add(arm["id"])
    expect(arm_ids, {"full", "catalog-only", "no-skill"}, "protocol.arms IDs")

    pairing = exact(protocol["pairing"], {"unit", "primary_comparison", "requires_same", "arm_order"}, "protocol.pairing")
    expect(pairing["unit"], "unique_case", "protocol.pairing.unit")
    expect(pairing["primary_comparison"], ["full", "no-skill"], "protocol.pairing.primary_comparison")
    if not isinstance(pairing["requires_same"], list) or not pairing["requires_same"]:
        fail("protocol.pairing.requires_same: expected controlled variables")

    identity = exact(
        protocol["execution_identity"],
        {"version_policy", "result_claim_scope", "runtime_overrides_forbidden", "primary", "primary_cell_requirement", "optional_replications"},
        "protocol.execution_identity",
    )
    expect(identity["version_policy"], "minimum", "protocol.execution_identity.version_policy")
    expect(identity["result_claim_scope"], "runner_and_model_specific", "protocol.execution_identity.result_claim_scope")
    primary = exact(identity["primary"], {"host_id", "runner_family", "model", "minimum_version"}, "protocol.execution_identity.primary")
    for key in ("host_id", "runner_family", "model", "minimum_version"):
        if not isinstance(primary[key], str) or not primary[key]:
            fail(f"protocol.execution_identity.primary.{key}: expected a preregistered non-empty string")
    optional_replications = exact(identity["optional_replications"], {"permitted_runner_families", "permitted_models", "contributes_to_primary_gate", "may_replace_or_rescue_primary_gate", "requires_separate_preregistration"}, "protocol.execution_identity.optional_replications")
    expect(optional_replications["contributes_to_primary_gate"], False, "protocol.execution_identity.optional_replications.contributes_to_primary_gate")
    expect(optional_replications["may_replace_or_rescue_primary_gate"], False, "protocol.execution_identity.optional_replications.may_replace_or_rescue_primary_gate")
    expect(optional_replications["requires_separate_preregistration"], True, "protocol.execution_identity.optional_replications.requires_separate_preregistration")

    schedule = exact(
        protocol["schedule"],
        {"unique_cases", "arm_count", "repetitions_per_case_arm", "scheduled_model_calls", "fresh_workspace_per_repetition", "repetitions_are_independent_samples", "repetition_purpose", "stable_prediction_rule", "invalid_or_unstable_handling"},
        "protocol.schedule",
    )
    expect(schedule["unique_cases"], 120, "protocol.schedule.unique_cases")
    expect(schedule["arm_count"], 3, "protocol.schedule.arm_count")
    expect(schedule["repetitions_per_case_arm"], 3, "protocol.schedule.repetitions_per_case_arm")
    expect(schedule["scheduled_model_calls"], 1080, "protocol.schedule.scheduled_model_calls")
    expect(schedule["fresh_workspace_per_repetition"], True, "protocol.schedule.fresh_workspace_per_repetition")
    expect(schedule["repetitions_are_independent_samples"], False, "protocol.schedule.repetitions_are_independent_samples")

    adjudication = exact(
        protocol["adjudication"],
        {"initial_adjudicators", "tie_breaker_adjudicators", "independent", "phases", "blinded_to", "response_order_randomized", "conflict_exclusions", "published_after_run"},
        "protocol.adjudication",
    )
    expect(adjudication["initial_adjudicators"], 2, "protocol.adjudication.initial_adjudicators")
    expect(adjudication["tie_breaker_adjudicators"], 1, "protocol.adjudication.tie_breaker_adjudicators")
    expect(adjudication["independent"], True, "protocol.adjudication.independent")
    phases = exact(adjudication["phases"], {"reference_oracle", "response_utility"}, "protocol.adjudication.phases")
    expect(
        exact(phases["reference_oracle"], {"timing", "model_outputs_visible", "authored_candidate_label_visible"}, "protocol.adjudication.phases.reference_oracle"),
        {"timing": "before_model_run", "model_outputs_visible": False, "authored_candidate_label_visible": False},
        "protocol.adjudication.phases.reference_oracle",
    )
    expect(
        exact(phases["response_utility"], {"timing", "final_oracle_visible", "arm_and_model_identity_visible"}, "protocol.adjudication.phases.response_utility"),
        {"timing": "after_model_run", "final_oracle_visible": True, "arm_and_model_identity_visible": False},
        "protocol.adjudication.phases.response_utility",
    )
    if not isinstance(adjudication["blinded_to"], list) or not adjudication["blinded_to"]:
        fail("protocol.adjudication.blinded_to: expected blinding contract")

    exact(protocol["user_helpfulness"], {"unit", "helpful_requires_all", "harmful_includes"}, "protocol.user_helpfulness")
    statistics = exact(protocol["statistics"], {"independent_unit", "repeated_runs_count_as_additional_cases", "confidence_interval", "paired_significance_test"}, "protocol.statistics")
    expect(statistics["independent_unit"], "unique_case", "protocol.statistics.independent_unit")
    expect(statistics["repeated_runs_count_as_additional_cases"], False, "protocol.statistics.repeated_runs_count_as_additional_cases")
    exact(statistics["confidence_interval"], {"method", "confidence", "iterations", "seed", "strata"}, "protocol.statistics.confidence_interval")
    exact(statistics["paired_significance_test"], {"method", "alpha", "direction_required"}, "protocol.statistics.paired_significance_test")

    decision = exact(protocol["decision"], {"requires_every_gate", "full_arm_absolute_thresholds", "primary_paired_lift_thresholds", "catalog_only_role", "rounding_policy"}, "protocol.decision")
    expect(decision["requires_every_gate"], True, "protocol.decision.requires_every_gate")
    if not isinstance(decision["full_arm_absolute_thresholds"], dict) or not decision["full_arm_absolute_thresholds"]:
        fail("protocol.decision.full_arm_absolute_thresholds: expected thresholds")
    if not isinstance(decision["primary_paired_lift_thresholds"], dict) or not decision["primary_paired_lift_thresholds"]:
        fail("protocol.decision.primary_paired_lift_thresholds: expected thresholds")

    evidence = exact(protocol["release_evidence"], {"development_only_unless_all_requirements_pass", "freeze_requires_clean_committed_tree", "required_custody", "required_attestation", "failure_status", "unsigned_provenance_is_attestation", "wrapper_name_or_local_path_is_isolation_proof"}, "protocol.release_evidence")
    expect(evidence["development_only_unless_all_requirements_pass"], True, "protocol.release_evidence.development_only_unless_all_requirements_pass")
    expect(evidence["freeze_requires_clean_committed_tree"], True, "protocol.release_evidence.freeze_requires_clean_committed_tree")
    custody = exact(evidence["required_custody"], {"external", "sealed", "custodian_independent_of_skill_authors", "operator_independent_of_skill_authors", "signed_corpus_commitment_before_execution", "corpus_revealed_only_inside_isolated_runner"}, "protocol.release_evidence.required_custody")
    if set(custody.values()) != {True}:
        fail("protocol.release_evidence.required_custody: every custody prerequisite must be true")
    attestation = exact(evidence["required_attestation"], {"machine_verifiable", "signature_algorithm", "digest_algorithm", "public_key_preregistered", "trusted_verifier_sha256", "preregistered_public_key_ed25519_base64", "binds"}, "protocol.release_evidence.required_attestation")
    expect(attestation["machine_verifiable"], True, "protocol.release_evidence.required_attestation.machine_verifiable")
    expect(attestation["signature_algorithm"], "Ed25519", "protocol.release_evidence.required_attestation.signature_algorithm")
    expect(attestation["digest_algorithm"], "SHA-256", "protocol.release_evidence.required_attestation.digest_algorithm")
    expect(attestation["public_key_preregistered"], True, "protocol.release_evidence.required_attestation.public_key_preregistered")
    for key in ("trusted_verifier_sha256", "preregistered_public_key_ed25519_base64"):
        if attestation[key] is not None and (not isinstance(attestation[key], str) or not attestation[key]):
            fail(f"protocol.release_evidence.required_attestation.{key}: expected null or a non-empty preregistered value")
    if attestation["trusted_verifier_sha256"] is not None:
        valid_sha256(attestation["trusted_verifier_sha256"], "protocol.release_evidence.required_attestation.trusted_verifier_sha256")
    public_key_pin = attestation["preregistered_public_key_ed25519_base64"]
    if public_key_pin is not None:
        try:
            decoded_key = base64.b64decode(public_key_pin, validate=True)
        except (ValueError, binascii.Error) as exc:
            fail(f"protocol.release_evidence.required_attestation.preregistered_public_key_ed25519_base64: invalid base64: {exc}")
        if len(decoded_key) != 32:
            fail("protocol.release_evidence.required_attestation.preregistered_public_key_ed25519_base64: Ed25519 public key must decode to 32 bytes")
    required_bindings = {"protocol", "evaluated_skill", "corpus_commitment", "runner_image", "model_identity", "all_inputs", "raw_outputs", "adjudication_ledger", "scorer_output"}
    expect(set(attestation["binds"]), required_bindings, "protocol.release_evidence.required_attestation.binds")
    expect(evidence["failure_status"], "INCONCLUSIVE", "protocol.release_evidence.failure_status")
    expect(evidence["unsigned_provenance_is_attestation"], False, "protocol.release_evidence.unsigned_provenance_is_attestation")
    expect(evidence["wrapper_name_or_local_path_is_isolation_proof"], False, "protocol.release_evidence.wrapper_name_or_local_path_is_isolation_proof")

    current = exact(protocol["current_evidence"], {"sealed_corpus", "signed_custody_commitment", "model_reports", "adjudication_ledger", "signed_isolation_attestation", "permitted_work"}, "protocol.current_evidence")
    if protocol["status"] == "NOT_RUN":
        expect(protocol["result"], "INCONCLUSIVE", "protocol.result while NOT_RUN")
        expect(current["model_reports"], 0, "protocol.current_evidence.model_reports while NOT_RUN")


def validate_ref(bundle: Path, value: Any, context: str) -> Path:
    ref = exact(value, {"path", "sha256"}, context)
    path = resolve_bundle_path(bundle, ref["path"], f"{context}.path")
    expected = valid_sha256(ref["sha256"], f"{context}.sha256")
    actual = sha256_file(path)
    if actual != expected:
        fail(f"{context}: SHA-256 mismatch; expected {expected}, got {actual}")
    return path


def validate_cases(bundle: Path, corpus: Any) -> tuple[str, set[str], set[str]]:
    corpus = exact(corpus, {"schema_version", "protocol_id", "corpus_id", "frozen_at", "cases"}, "corpus")
    expect(corpus["schema_version"], 1, "corpus.schema_version")
    expect(corpus["protocol_id"], "reviewer-release-v1", "corpus.protocol_id")
    corpus_id = corpus["corpus_id"]
    if not isinstance(corpus_id, str) or not corpus_id:
        fail("corpus.corpus_id: expected a non-empty string")
    cases = corpus["cases"]
    if not isinstance(cases, list) or len(cases) != 120:
        fail("corpus.cases: expected exactly 120 cases")

    case_ids: set[str] = set()
    units: set[tuple[str, str]] = set()
    repo_counts: dict[str, int] = {}
    frameworks = {"playwright": 0, "cypress": 0}
    kinds = {"positive": 0, "clean": 0}
    positive_ids: set[str] = set()
    source_paths: set[str] = set()
    positive_pattern_counts = {pattern_id: 0 for pattern_id in TAXONOMY}
    guard_case_ids = {pattern_id: set() for pattern_id in TAXONOMY}
    positive_severity_counts = {"P0": 0, "P1": 0, "P2": 0}
    for index, raw in enumerate(cases):
        context = f"corpus.cases[{index}]"
        case = exact(raw, {"case_id", "repo_id", "framework", "kind", "source", "taxonomy_id", "severity", "guard_taxonomy_ids"}, context)
        case_id, repo_id = case["case_id"], case["repo_id"]
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            fail(f"{context}.case_id: expected a unique non-empty ID")
        if not isinstance(repo_id, str) or not repo_id:
            fail(f"{context}.repo_id: expected a non-empty ID")
        unit = (repo_id, case_id)
        if unit in units:
            fail(f"{context}: duplicate repo/case unit")
        case_ids.add(case_id)
        units.add(unit)
        repo_counts[repo_id] = repo_counts.get(repo_id, 0) + 1
        if repo_counts[repo_id] > 2:
            fail(f"{context}.repo_id: more than two cases use repository {repo_id!r}")
        if case["framework"] not in frameworks:
            fail(f"{context}.framework: expected playwright or cypress")
        frameworks[case["framework"]] += 1
        if case["kind"] not in kinds:
            fail(f"{context}.kind: expected positive or clean")
        kinds[case["kind"]] += 1
        source_ref = exact(case["source"], {"path", "sha256"}, f"{context}.source")
        source_path = source_ref["path"]
        if source_path in source_paths:
            fail(f"{context}.source.path: source paths must be unique")
        source_paths.add(source_path)
        validate_ref(bundle, source_ref, f"{context}.source")
        if case["kind"] == "positive":
            pattern_id = case["taxonomy_id"]
            if pattern_id not in TAXONOMY:
                fail(f"{context}.taxonomy_id: unknown stable taxonomy ID {pattern_id!r}")
            expect(case["severity"], TAXONOMY[pattern_id], f"{context}.severity")
            expect(case["guard_taxonomy_ids"], [], f"{context}.guard_taxonomy_ids")
            positive_ids.add(case_id)
            positive_pattern_counts[pattern_id] += 1
            positive_severity_counts[case["severity"]] += 1
        elif case["taxonomy_id"] is not None or case["severity"] is not None:
            fail(f"{context}: clean cases must have null taxonomy_id and severity")
        else:
            guards = case["guard_taxonomy_ids"]
            if not isinstance(guards, list) or len(guards) != len(set(guards)):
                fail(f"{context}.guard_taxonomy_ids: expected unique stable taxonomy IDs")
            for pattern_id in guards:
                if pattern_id not in TAXONOMY:
                    fail(f"{context}.guard_taxonomy_ids: unknown stable taxonomy ID {pattern_id!r}")
                guard_case_ids[pattern_id].add(case_id)
    expect(frameworks, {"playwright": 60, "cypress": 60}, "corpus framework balance")
    expect(kinds, {"positive": 60, "clean": 60}, "corpus label balance")
    for pattern_id, count in positive_pattern_counts.items():
        if count < 2:
            fail(f"corpus taxonomy coverage: pattern {pattern_id} has {count} positive opportunities; minimum is 2")
    for pattern_id, guards in guard_case_ids.items():
        if len(guards) < 2:
            fail(f"corpus guard coverage: pattern {pattern_id} has {len(guards)} distinct clean/near-miss cases; minimum is 2")
    for severity, count in positive_severity_counts.items():
        if count < 10:
            fail(f"corpus severity coverage: {severity} has {count} positive cases; minimum is 10")
    return corpus_id, case_ids, positive_ids


def validate_labels(labels: Any, corpus_id: str, case_ids: set[str], positive_ids: set[str]) -> None:
    labels = exact(labels, {"schema_version", "corpus_id", "model_visible", "labels"}, "labels")
    expect(labels["schema_version"], 1, "labels.schema_version")
    expect(labels["corpus_id"], corpus_id, "labels.corpus_id")
    expect(labels["model_visible"], False, "labels.model_visible")
    rows = labels["labels"]
    if not isinstance(rows, list) or len(rows) != 120:
        fail("labels.labels: expected exactly 120 labels")
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        context = f"labels.labels[{index}]"
        row = exact(raw, {"case_id", "kind", "taxonomy_id", "severity"}, context)
        case_id = row["case_id"]
        if case_id not in case_ids or case_id in seen:
            fail(f"{context}.case_id: unknown or duplicate case")
        seen.add(case_id)
        if case_id in positive_ids:
            expect(row["kind"], "positive", f"{context}.kind")
            pattern_id = row["taxonomy_id"]
            if pattern_id not in TAXONOMY:
                fail(f"{context}.taxonomy_id: unknown stable taxonomy ID")
            expect(row["severity"], TAXONOMY[pattern_id], f"{context}.severity")
        elif row != {"case_id": case_id, "kind": "clean", "taxonomy_id": None, "severity": None}:
            fail(f"{context}: clean label must contain only null taxonomy data")
    if seen != case_ids:
        fail("labels.labels: label set does not exactly cover the corpus")


def adjudicator_vote(value: Any, context: str) -> tuple[str, Any, Any]:
    vote = exact(value, {"reviewer_id", "blinded", "kind", "taxonomy_id", "severity", "recorded_at"}, context)
    if not isinstance(vote["reviewer_id"], str) or not vote["reviewer_id"]:
        fail(f"{context}.reviewer_id: expected a non-empty string")
    expect(vote["blinded"], True, f"{context}.blinded")
    if vote["kind"] not in {"positive", "clean"}:
        fail(f"{context}.kind: expected positive or clean")
    if vote["kind"] == "positive":
        if vote["taxonomy_id"] not in TAXONOMY:
            fail(f"{context}.taxonomy_id: unknown stable taxonomy ID")
        expect(vote["severity"], TAXONOMY[vote["taxonomy_id"]], f"{context}.severity")
    elif vote["taxonomy_id"] is not None or vote["severity"] is not None:
        fail(f"{context}: clean vote must have null taxonomy data")
    if not isinstance(vote["recorded_at"], str) or not vote["recorded_at"]:
        fail(f"{context}.recorded_at: expected a timestamp")
    return vote["kind"], vote["taxonomy_id"], vote["severity"]


def validate_adjudications(value: Any, corpus_id: str, case_ids: set[str]) -> None:
    data = exact(value, {"schema_version", "corpus_id", "completed_before_model_run", "model_outputs_seen", "records"}, "adjudications")
    expect(data["schema_version"], 1, "adjudications.schema_version")
    expect(data["corpus_id"], corpus_id, "adjudications.corpus_id")
    expect(data["completed_before_model_run"], True, "adjudications.completed_before_model_run")
    expect(data["model_outputs_seen"], False, "adjudications.model_outputs_seen")
    records = data["records"]
    if not isinstance(records, list) or len(records) != 120:
        fail("adjudications.records: expected exactly 120 records")
    seen: set[str] = set()
    for index, raw in enumerate(records):
        context = f"adjudications.records[{index}]"
        row = exact(raw, {"case_id", "reviewer_1", "reviewer_2", "tie_break"}, context)
        case_id = row["case_id"]
        if case_id not in case_ids or case_id in seen:
            fail(f"{context}.case_id: unknown or duplicate case")
        seen.add(case_id)
        first = adjudicator_vote(row["reviewer_1"], f"{context}.reviewer_1")
        second = adjudicator_vote(row["reviewer_2"], f"{context}.reviewer_2")
        if row["reviewer_1"]["reviewer_id"] == row["reviewer_2"]["reviewer_id"]:
            fail(f"{context}: the two human adjudications must be independent")
        disagree = first != second
        if disagree and row["tie_break"] is None:
            fail(f"{context}.tie_break: required when reviewers disagree")
        if not disagree and row["tie_break"] is not None:
            fail(f"{context}.tie_break: must be null when reviewers agree")
        if row["tie_break"] is not None:
            tie = adjudicator_vote(row["tie_break"], f"{context}.tie_break")
            if row["tie_break"]["reviewer_id"] in {row["reviewer_1"]["reviewer_id"], row["reviewer_2"]["reviewer_id"]}:
                fail(f"{context}.tie_break: tie-breaker must be a third reviewer")
            if tie not in {first, second}:
                fail(f"{context}.tie_break: verdict must resolve to one submitted vote")


def validate_custody(value: Any, corpus_id: str) -> None:
    data = exact(value, {"schema_version", "corpus_id", "sealed_before_model_run", "model_access", "custodian", "events"}, "custody")
    expect(data["schema_version"], 1, "custody.schema_version")
    expect(data["corpus_id"], corpus_id, "custody.corpus_id")
    expect(data["sealed_before_model_run"], True, "custody.sealed_before_model_run")
    expect(data["model_access"], False, "custody.model_access")
    if not isinstance(data["custodian"], str) or not data["custodian"]:
        fail("custody.custodian: expected a non-empty external custodian")
    if not isinstance(data["events"], list) or not data["events"]:
        fail("custody.events: expected a non-empty custody ledger")
    for index, raw in enumerate(data["events"]):
        event = exact(raw, {"event_id", "timestamp", "actor", "action", "artifact_sha256"}, f"custody.events[{index}]")
        for key in ("event_id", "timestamp", "actor", "action"):
            if not isinstance(event[key], str) or not event[key]:
                fail(f"custody.events[{index}].{key}: expected a non-empty string")
        valid_sha256(event["artifact_sha256"], f"custody.events[{index}].artifact_sha256")


def verify_isolation(
    bundle: Path,
    isolation: Any,
    protocol_id: str,
    corpus_id: str,
    verifier: Path,
    verifier_sha256: str,
    public_key: str,
) -> None:
    isolation = exact(isolation, {"attestation"}, "bundle.isolation")
    attestation = validate_ref(bundle, isolation["attestation"], "bundle.isolation.attestation")
    if not verifier.is_absolute():
        fail("trusted attestation verifier must use an absolute path")
    verifier = verifier.resolve()
    if not verifier.is_file():
        fail("trusted attestation verifier must be an existing absolute file")
    try:
        verifier.relative_to(bundle.resolve())
    except ValueError:
        pass
    else:
        fail("trusted attestation verifier must be external to the untrusted bundle")
    if sha256_file(verifier) != verifier_sha256:
        fail("trusted attestation verifier SHA-256 does not match the preregistered protocol pin")
    if not os.access(verifier, os.X_OK):
        fail("trusted attestation verifier is not executable")
    expected_attestation_hash = sha256_file(attestation)
    try:
        completed = subprocess.run(
            [str(verifier), "--attestation", str(attestation), "--bundle", str(bundle), "--public-key", public_key],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env={
                "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
                "LANG": "C",
                "LC_ALL": "C",
            },
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"bundle.isolation.verifier: could not complete verification: {exc}")
    if completed.returncode != 0:
        fail(f"bundle.isolation.verifier: rejected attestation (exit {completed.returncode})")
    try:
        from strict_json import loads_strict

        result = loads_strict(completed.stdout, context="isolation verifier stdout")
    except StrictJsonError as exc:
        raise ValidationError(str(exc)) from exc
    result = exact(result, {"verified", "protocol_id", "corpus_id", "attestation_sha256"}, "isolation verifier result")
    expect(result["verified"], True, "isolation verifier result.verified")
    expect(result["protocol_id"], protocol_id, "isolation verifier result.protocol_id")
    expect(result["corpus_id"], corpus_id, "isolation verifier result.corpus_id")
    expect(result["attestation_sha256"], expected_attestation_hash, "isolation verifier result.attestation_sha256")


def validate_bundle(bundle: Path, verifier: Path, verifier_sha256: str, public_key: str) -> None:
    bundle = bundle.resolve()
    if not bundle.is_dir():
        fail(f"external bundle directory does not exist: {bundle}")
    manifest = load_json(bundle / "bundle.json")
    manifest = exact(manifest, {"schema_version", "protocol_id", "corpus", "labels", "adjudications", "custody", "isolation"}, "bundle")
    expect(manifest["schema_version"], 1, "bundle.schema_version")
    expect(manifest["protocol_id"], "reviewer-release-v1", "bundle.protocol_id")
    corpus_path = validate_ref(bundle, manifest["corpus"], "bundle.corpus")
    labels_path = validate_ref(bundle, manifest["labels"], "bundle.labels")
    adjudications_path = validate_ref(bundle, manifest["adjudications"], "bundle.adjudications")
    custody_path = validate_ref(bundle, manifest["custody"], "bundle.custody")
    referenced = {corpus_path, labels_path, adjudications_path, custody_path}
    if len(referenced) != 4:
        fail("bundle: corpus, labels, adjudications, and custody must be separate files")
    corpus_id, case_ids, positive_ids = validate_cases(bundle, load_json(corpus_path))
    validate_labels(load_json(labels_path), corpus_id, case_ids, positive_ids)
    validate_adjudications(load_json(adjudications_path), corpus_id, case_ids)
    validate_custody(load_json(custody_path), corpus_id)
    verify_isolation(bundle, manifest["isolation"], "reviewer-release-v1", corpus_id, verifier, verifier_sha256, public_key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--protocol-only", action="store_true")
    mode.add_argument("--bundle", type=Path)
    parser.add_argument("--attestation-verifier", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        protocol = load_json(args.protocol.resolve())
        validate_protocol(protocol)
        if args.protocol_only:
            print("reviewer-release-v1 validation: PASS (protocol-only)")
            return 0
        if protocol["status"] not in {"FROZEN", "COMPLETE"}:
            fail("release-ready validation requires protocol.status FROZEN or COMPLETE")
        if args.attestation_verifier is None:
            fail("release-ready validation requires --attestation-verifier")
        attestation_contract = protocol["release_evidence"]["required_attestation"]
        verifier_sha256 = attestation_contract["trusted_verifier_sha256"]
        public_key = attestation_contract["preregistered_public_key_ed25519_base64"]
        if verifier_sha256 is None or public_key is None:
            fail("release-ready validation is blocked until verifier SHA-256 and Ed25519 public key are preregistered")
        validate_bundle(args.bundle, args.attestation_verifier, verifier_sha256, public_key)
    except ValidationError as exc:
        print(f"reviewer-release-v1 validation: FAIL: {exc}", file=sys.stderr)
        return 1
    print("reviewer-release-v1 validation: PASS (release-ready)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
