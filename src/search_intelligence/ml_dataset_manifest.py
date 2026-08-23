from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Final

from src.search_intelligence.ml_foundation import (
    TrainingDatasetContract,
    validate_training_dataset_contract,
)


DATASET_MANIFEST_SCHEMA_VERSION: Final[str] = "ml-training-dataset-manifest/v1"
_DATASET_FIELDS: Final[frozenset[str]] = frozenset(TrainingDatasetContract.__dataclass_fields__)
_ENVELOPE_FIELDS: Final[frozenset[str]] = frozenset(
    {"schema_version", "dataset", "content_fingerprint"}
)


@dataclass(frozen=True)
class TrainingDatasetManifest:
    contract: TrainingDatasetContract
    schema_version: str = DATASET_MANIFEST_SCHEMA_VERSION


def validate_training_dataset_manifest(manifest: TrainingDatasetManifest) -> list[str]:
    violations = validate_training_dataset_contract(manifest.contract)
    if manifest.schema_version != DATASET_MANIFEST_SCHEMA_VERSION:
        violations.append(
            "schema_version must be "
            f"{DATASET_MANIFEST_SCHEMA_VERSION!r}; got {manifest.schema_version!r}."
        )
    return violations


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _fingerprint_payload(manifest: TrainingDatasetManifest) -> dict[str, Any]:
    return {
        "schema_version": manifest.schema_version,
        "dataset": asdict(manifest.contract),
    }


def fingerprint_training_dataset_manifest(manifest: TrainingDatasetManifest) -> str:
    violations = validate_training_dataset_manifest(manifest)
    if violations:
        raise ValueError("; ".join(violations))
    payload = _canonical_json(_fingerprint_payload(manifest)).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def serialize_training_dataset_manifest(manifest: TrainingDatasetManifest) -> str:
    fingerprint = fingerprint_training_dataset_manifest(manifest)
    envelope = {
        **_fingerprint_payload(manifest),
        "content_fingerprint": fingerprint,
    }
    return _canonical_json(envelope)


def deserialize_training_dataset_manifest(text: str) -> TrainingDatasetManifest:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid training dataset manifest JSON: {exc.msg}.") from exc

    if not isinstance(raw, dict):
        raise ValueError("Training dataset manifest must be a JSON object.")

    envelope_fields = frozenset(raw)
    if envelope_fields != _ENVELOPE_FIELDS:
        missing = sorted(_ENVELOPE_FIELDS - envelope_fields)
        extra = sorted(envelope_fields - _ENVELOPE_FIELDS)
        raise ValueError(
            "Training dataset manifest envelope fields mismatch; "
            f"missing={missing}, extra={extra}."
        )

    schema_version = raw["schema_version"]
    if not isinstance(schema_version, str):
        raise ValueError("Training dataset manifest schema_version must be a string.")
    if schema_version != DATASET_MANIFEST_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported training dataset manifest schema_version "
            f"{schema_version!r}; expected {DATASET_MANIFEST_SCHEMA_VERSION!r}."
        )

    dataset = raw["dataset"]
    if not isinstance(dataset, dict):
        raise ValueError("Training dataset manifest 'dataset' must be a JSON object.")

    dataset_fields = frozenset(dataset)
    if dataset_fields != _DATASET_FIELDS:
        missing = sorted(_DATASET_FIELDS - dataset_fields)
        extra = sorted(dataset_fields - _DATASET_FIELDS)
        raise ValueError(
            "Training dataset manifest dataset fields mismatch; "
            f"missing={missing}, extra={extra}."
        )

    non_string_fields = sorted(
        field_name for field_name, value in dataset.items() if not isinstance(value, str)
    )
    if non_string_fields:
        raise ValueError(
            "Training dataset manifest dataset values must be strings; "
            f"invalid={non_string_fields}."
        )

    contract = TrainingDatasetContract(**dataset)
    manifest = TrainingDatasetManifest(contract=contract, schema_version=schema_version)
    violations = validate_training_dataset_manifest(manifest)
    if violations:
        raise ValueError("; ".join(violations))

    claimed_fingerprint = raw["content_fingerprint"]
    if not isinstance(claimed_fingerprint, str):
        raise ValueError("Training dataset manifest content_fingerprint must be a string.")
    expected_fingerprint = fingerprint_training_dataset_manifest(manifest)
    if claimed_fingerprint != expected_fingerprint:
        raise ValueError(
            "Training dataset manifest content_fingerprint mismatch; "
            f"expected {expected_fingerprint!r}."
        )

    return manifest
