#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Mutation tests for the reviewer release-v1 fail-closed validator."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "scripts" / "evals" / "validate-reviewer-release-v1.py"
PROTOCOL_PATH = ROOT / "scripts" / "evals" / "reviewer-release-v1-protocol.json"
SPEC = importlib.util.spec_from_file_location("reviewer_release_v1_validator", VALIDATOR_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path: Path, root: Path) -> dict[str, str]:
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(path)}


def vote(reviewer_id: str, kind: str, taxonomy_id: str | None, severity: str | None) -> dict[str, Any]:
    return {
        "reviewer_id": reviewer_id,
        "blinded": True,
        "kind": kind,
        "taxonomy_id": taxonomy_id,
        "severity": severity,
        "recorded_at": "2026-09-01T00:00:00Z",
    }


def make_bundle(root: Path) -> dict[str, Any]:
    taxonomy = list(VALIDATOR.TAXONOMY.items())
    taxonomy_ids = [pattern_id for pattern_id, _severity in taxonomy]
    p0_ids = [pattern_id for pattern_id, severity in taxonomy if severity == "P0"]
    p2_ids = [pattern_id for pattern_id, severity in taxonomy if severity == "P2"]
    positive_patterns = taxonomy_ids * 2 + p0_ids[:4] + p2_ids * 2 + p2_ids[:2]
    assert len(positive_patterns) == 60
    cases: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    adjudications: list[dict[str, Any]] = []
    positive_index = 0
    clean_index = 0
    for index in range(120):
        case_id = f"case-{index + 1:03d}"
        framework = "playwright" if index < 60 else "cypress"
        positive = index % 60 < 30
        kind = "positive" if positive else "clean"
        if positive:
            taxonomy_id = positive_patterns[positive_index]
            severity = VALIDATOR.TAXONOMY[taxonomy_id]
            guard_taxonomy_ids: list[str] = []
            positive_index += 1
        else:
            taxonomy_id, severity = None, None
            guard_taxonomy_ids = [
                taxonomy_ids[clean_index % len(taxonomy_ids)],
                taxonomy_ids[(clean_index + 12) % len(taxonomy_ids)],
            ]
            clean_index += 1
        source = root / "sources" / f"{case_id}.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"synthetic source {case_id}\n", encoding="utf-8")
        cases.append(
            {
                "case_id": case_id,
                "repo_id": f"repo-{index // 2 + 1:03d}",
                "framework": framework,
                "kind": kind,
                "source": ref(source, root),
                "taxonomy_id": taxonomy_id,
                "severity": severity,
                "guard_taxonomy_ids": guard_taxonomy_ids,
            }
        )
        labels.append(
            {
                "case_id": case_id,
                "kind": kind,
                "taxonomy_id": taxonomy_id,
                "severity": severity,
            }
        )
        first = vote("human-a", kind, taxonomy_id, severity)
        second = vote("human-b", kind, taxonomy_id, severity)
        adjudications.append(
            {"case_id": case_id, "reviewer_1": first, "reviewer_2": second, "tie_break": None}
        )

    corpus_path = root / "corpus.json"
    labels_path = root / "labels.json"
    adjudications_path = root / "adjudications.json"
    custody_path = root / "custody.json"
    dump(
        corpus_path,
        {
            "schema_version": 1,
            "protocol_id": "reviewer-release-v1",
            "corpus_id": "external-corpus-001",
            "frozen_at": "2026-09-01T00:00:00Z",
            "cases": cases,
        },
    )
    dump(
        labels_path,
        {"schema_version": 1, "corpus_id": "external-corpus-001", "model_visible": False, "labels": labels},
    )
    dump(
        adjudications_path,
        {
            "schema_version": 1,
            "corpus_id": "external-corpus-001",
            "completed_before_model_run": True,
            "model_outputs_seen": False,
            "records": adjudications,
        },
    )
    dump(
        custody_path,
        {
            "schema_version": 1,
            "corpus_id": "external-corpus-001",
            "sealed_before_model_run": True,
            "model_access": False,
            "custodian": "independent-custodian",
            "events": [
                {
                    "event_id": "freeze-001",
                    "timestamp": "2026-09-01T00:00:00Z",
                    "actor": "independent-custodian",
                    "action": "sealed corpus and oracle",
                    "artifact_sha256": digest(corpus_path),
                }
            ],
        },
    )
    attestation = root / "isolation.attestation"
    attestation.write_text("signed-attestation-placeholder\n", encoding="utf-8")
    verifier = root.parent / f"verify-attestation-{root.name}"
    verifier.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' '{{\"verified\":true,\"protocol_id\":\"reviewer-release-v1\",\"corpus_id\":\"external-corpus-001\",\"attestation_sha256\":\"{digest(attestation)}\"}}'\n",
        encoding="utf-8",
    )
    verifier.chmod(0o700)
    manifest = {
        "schema_version": 1,
        "protocol_id": "reviewer-release-v1",
        "corpus": ref(corpus_path, root),
        "labels": ref(labels_path, root),
        "adjudications": ref(adjudications_path, root),
        "custody": ref(custody_path, root),
        "isolation": {"attestation": ref(attestation, root)},
    }
    dump(root / "bundle.json", manifest)
    return manifest


def expect_error(action: Callable[[], Any], needle: str) -> None:
    try:
        action()
    except VALIDATOR.ValidationError as exc:
        assert needle in str(exc), (needle, str(exc))
    else:
        raise AssertionError(f"expected ValidationError containing {needle!r}")


def mutate_json(path: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    mutation(value)
    dump(path, value)


def refresh_manifest_ref(root: Path, key: str, path: Path) -> None:
    mutate_json(root / "bundle.json", lambda value: value.__setitem__(key, ref(path, root)))


def bundle_root(directory: str) -> Path:
    root = Path(directory) / "bundle"
    root.mkdir()
    return root


def trusted_verifier(root: Path) -> Path:
    return root.parent / f"verify-attestation-{root.name}"


def test_protocol_only_accepts_frozen_contract() -> None:
    VALIDATOR.validate_protocol(VALIDATOR.load_json(PROTOCOL_PATH))
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--protocol-only"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "PASS (protocol-only)" in completed.stdout


def test_protocol_rejects_duplicate_keys() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "duplicate.json"
        path.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
        expect_error(lambda: VALIDATOR.load_json(path), "duplicate JSON object key")


def test_protocol_mutations_fail_closed() -> None:
    protocol = VALIDATOR.load_json(PROTOCOL_PATH)
    mutations = (
        (lambda value: value.__setitem__("unexpected", True), "unknown=['unexpected']"),
        (lambda value: value["corpus"].__setitem__("unique_cases", 119), "expected 120"),
        (lambda value: value["corpus"]["frameworks"]["playwright"].__setitem__("clean", 29), "expected {'positive': 30, 'clean': 30}"),
        (lambda value: value["execution_identity"].__setitem__("version_policy", "exact"), "expected 'minimum'"),
        (lambda value: value["execution_identity"]["primary"].__setitem__("model", ""), "expected a preregistered"),
        (lambda value: value["schedule"].__setitem__("scheduled_model_calls", 360), "expected 1080"),
        (lambda value: value["adjudication"]["phases"]["response_utility"].__setitem__("arm_and_model_identity_visible", True), "expected {'timing': 'after_model_run'"),
        (lambda value: value["release_evidence"]["required_custody"].__setitem__("sealed", False), "custody prerequisite"),
        (lambda value: value["release_evidence"]["required_attestation"].__setitem__("signature_algorithm", "none"), "expected 'Ed25519'"),
    )
    for mutate, needle in mutations:
        changed = copy.deepcopy(protocol)
        mutate(changed)
        expect_error(lambda changed=changed: VALIDATOR.validate_protocol(changed), needle)


def test_valid_external_bundle_and_attestation_pass() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_bundle(root)
        verifier = trusted_verifier(root)
        VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key")


def test_corpus_mutations_fail_closed() -> None:
    mutations = (
        (lambda value: value["cases"].pop(), "exactly 120 cases"),
        (lambda value: value["cases"][1].__setitem__("case_id", value["cases"][0]["case_id"]), "unique non-empty ID"),
        (lambda value: value["cases"][2].__setitem__("repo_id", value["cases"][0]["repo_id"]), "more than two cases"),
        (lambda value: value["cases"][0].__setitem__("severity", "P2"), "expected 'P0'"),
    )
    for mutate, needle in mutations:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_bundle(root)
            path = root / "corpus.json"
            mutate_json(path, mutate)
            refresh_manifest_ref(root, "corpus", path)
            verifier = trusted_verifier(root)
            expect_error(lambda root=root, verifier=verifier: VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key"), needle)


def test_source_hash_mismatch_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_bundle(root)
        (root / "sources" / "case-001.txt").write_text("mutated after freeze\n", encoding="utf-8")
        verifier = trusted_verifier(root)
        expect_error(lambda: VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key"), "SHA-256 mismatch")


def test_labels_must_be_separate_hidden_and_complete() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_bundle(root)
        labels_path = root / "labels.json"
        mutate_json(labels_path, lambda value: value.__setitem__("model_visible", True))
        refresh_manifest_ref(root, "labels", labels_path)
        verifier = trusted_verifier(root)
        expect_error(lambda: VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key"), "expected False")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        manifest = make_bundle(root)
        manifest["labels"] = manifest["corpus"]
        dump(root / "bundle.json", manifest)
        verifier = trusted_verifier(root)
        expect_error(lambda: VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key"), "must be separate files")


def test_two_blinded_independent_adjudications_required() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_bundle(root)
        path = root / "adjudications.json"
        mutate_json(path, lambda value: value["records"][0]["reviewer_2"].__setitem__("reviewer_id", "human-a"))
        refresh_manifest_ref(root, "adjudications", path)
        verifier = trusted_verifier(root)
        expect_error(lambda: VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key"), "must be independent")


def test_disagreement_requires_third_party_tie_break() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_bundle(root)
        path = root / "adjudications.json"
        def disagree(value: dict[str, Any]) -> None:
            value["records"][0]["reviewer_2"].update({"kind": "clean", "taxonomy_id": None, "severity": None})
        mutate_json(path, disagree)
        refresh_manifest_ref(root, "adjudications", path)
        verifier = trusted_verifier(root)
        expect_error(lambda: VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key"), "required when reviewers disagree")


def test_custody_manifest_is_mandatory_and_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_bundle(root)
        path = root / "custody.json"
        mutate_json(path, lambda value: value.__setitem__("sealed_before_model_run", False))
        refresh_manifest_ref(root, "custody", path)
        verifier = trusted_verifier(root)
        expect_error(lambda: VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key"), "expected True")


def test_signed_isolation_verifier_must_verify_exact_attestation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        make_bundle(root)
        verifier = trusted_verifier(root)
        verifier.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        verifier.chmod(0o700)
        expect_error(lambda: VALIDATOR.validate_bundle(root, verifier, digest(verifier), "test-public-key"), "rejected attestation")


def test_signed_isolation_verifier_ignores_ambient_path() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "bundle"
        hostile_bin = Path(directory) / "hostile-bin"
        root.mkdir()
        hostile_bin.mkdir()
        make_bundle(root)
        attestation = root / "isolation.attestation"
        helper = hostile_bin / "fake-attestation-helper"
        helper.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' '{{\"verified\":true,\"protocol_id\":\"reviewer-release-v1\",\"corpus_id\":\"external-corpus-001\",\"attestation_sha256\":\"{digest(attestation)}\"}}'\n",
            encoding="utf-8",
        )
        helper.chmod(0o700)
        verifier = trusted_verifier(root)
        verifier.write_text("#!/bin/sh\nexec fake-attestation-helper\n", encoding="utf-8")
        verifier.chmod(0o700)
        previous_path = os.environ.get("PATH")
        os.environ["PATH"] = f"{hostile_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
        try:
            expect_error(
                lambda: VALIDATOR.validate_bundle(
                    root, verifier, digest(verifier), "test-public-key"
                ),
                "rejected attestation",
            )
        finally:
            if previous_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = previous_path


def test_cli_refuses_release_ready_without_bundle() -> None:
    completed = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--bundle", "/definitely/missing/reviewer-release-v1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "release-ready validation requires" in completed.stderr


def main() -> None:
    tests = [
        test_protocol_only_accepts_frozen_contract,
        test_protocol_rejects_duplicate_keys,
        test_protocol_mutations_fail_closed,
        test_valid_external_bundle_and_attestation_pass,
        test_corpus_mutations_fail_closed,
        test_source_hash_mismatch_fails_closed,
        test_labels_must_be_separate_hidden_and_complete,
        test_two_blinded_independent_adjudications_required,
        test_disagreement_requires_third_party_tie_break,
        test_custody_manifest_is_mandatory_and_fail_closed,
        test_signed_isolation_verifier_must_verify_exact_attestation,
        test_signed_isolation_verifier_ignores_ambient_path,
        test_cli_refuses_release_ready_without_bundle,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print(f"reviewer release-v1 validator tests: {len(tests)} passed")


if __name__ == "__main__":
    main()
