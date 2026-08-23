from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.search_intelligence.ml_dataset_manifest import (
    DATASET_MANIFEST_SCHEMA_VERSION,
    TrainingDatasetManifest,
    deserialize_training_dataset_manifest,
    fingerprint_training_dataset_manifest,
    serialize_training_dataset_manifest,
    validate_training_dataset_manifest,
)
from src.search_intelligence.ml_foundation import TrainingDatasetContract


FIXTURE_PATH = Path("tests/fixtures/ml/training_dataset_manifest_v1.json")
EXPECTED_FINGERPRINT = "sha256:66a3f5b86b482d89d97f40afd2fac8e6d84666995e64d44cb281cc85529b039d"


def _contract() -> TrainingDatasetContract:
    return TrainingDatasetContract(
        dataset_version="jobs-v1",
        feature_contract_version="features-v1",
        product_contract_version="prd-v1",
        source_snapshot="postgres://snapshot/2026-08-23T14:30:00Z",
        code_commit="0123456789abcdef",
        split_strategy="grouped-by-job-family-v1",
        label_provenance="operator-reviewed-v1",
    )


def test_manifest_serialization_matches_frozen_fixture_and_round_trips() -> None:
    manifest = TrainingDatasetManifest(contract=_contract())

    serialized = serialize_training_dataset_manifest(manifest)

    assert serialized == FIXTURE_PATH.read_text(encoding="utf-8").strip()
    assert deserialize_training_dataset_manifest(serialized) == manifest


def test_manifest_fingerprint_is_stable_and_content_addressed() -> None:
    manifest = TrainingDatasetManifest(contract=_contract())

    first = fingerprint_training_dataset_manifest(manifest)
    second = fingerprint_training_dataset_manifest(
        deserialize_training_dataset_manifest(serialize_training_dataset_manifest(manifest))
    )

    assert first == EXPECTED_FINGERPRINT
    assert second == first
    assert first.startswith("sha256:")


def test_manifest_validation_rejects_unknown_schema_version() -> None:
    manifest = TrainingDatasetManifest(
        contract=_contract(),
        schema_version="ml-training-dataset-manifest/v2",
    )

    violations = validate_training_dataset_manifest(manifest)

    assert violations == [
        "schema_version must be "
        f"{DATASET_MANIFEST_SCHEMA_VERSION!r}; got 'ml-training-dataset-manifest/v2'."
    ]
    with pytest.raises(ValueError, match="schema_version must be"):
        serialize_training_dataset_manifest(manifest)


def test_manifest_deserializer_rejects_tampering_with_stale_fingerprint() -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    raw["dataset"]["dataset_version"] = "jobs-v2"
    tampered = json.dumps(raw, sort_keys=True, separators=(",", ":"))

    with pytest.raises(ValueError, match="content_fingerprint mismatch"):
        deserialize_training_dataset_manifest(tampered)


def test_manifest_deserializer_rejects_unknown_or_missing_fields() -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    raw["dataset"]["manual_notes"] = "not part of v1"

    with pytest.raises(ValueError, match="dataset fields mismatch"):
        deserialize_training_dataset_manifest(json.dumps(raw))

    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    del raw["content_fingerprint"]

    with pytest.raises(ValueError, match="envelope fields mismatch"):
        deserialize_training_dataset_manifest(json.dumps(raw))


def test_manifest_deserializer_rejects_non_string_dataset_values() -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    raw["dataset"]["dataset_version"] = 2

    with pytest.raises(ValueError, match="dataset values must be strings"):
        deserialize_training_dataset_manifest(json.dumps(raw))


def test_manifest_deserializer_preserves_kaggle_training_platform_boundary() -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    raw["dataset"]["training_platform"] = "local-notebook"
    raw["content_fingerprint"] = EXPECTED_FINGERPRINT

    with pytest.raises(ValueError, match="training_platform must be 'kaggle'"):
        deserialize_training_dataset_manifest(json.dumps(raw))
