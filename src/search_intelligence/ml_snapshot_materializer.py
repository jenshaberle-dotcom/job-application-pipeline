from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
from typing import Any, Final

from src.search_intelligence.ml_dataset_manifest import (
    TrainingDatasetManifest,
    fingerprint_training_dataset_manifest,
    serialize_training_dataset_manifest,
)
from src.search_intelligence.ml_experiment_transport import (
    CpuValidationReport,
    TrainingPackageManifest,
    build_training_package_entry,
    fingerprint_bytes,
    fingerprint_training_package_manifest,
    serialize_training_package_manifest,
    validate_training_package_contents,
)
from src.search_intelligence.ml_foundation import TrainingDatasetContract
from src.search_intelligence.ml_snapshot_plan import (
    SNAPSHOT_ISOLATION_LEVEL,
    SNAPSHOT_SOURCE_RELATION,
    TrainingSnapshotPlan,
    build_training_snapshot_sql,
    default_training_snapshot_plan,
    fingerprint_training_snapshot_plan,
    read_only_transaction_preamble,
    snapshot_column_names,
)


MATERIALIZATION_SCHEMA_VERSION: Final[str] = "ml-snapshot-materialization/v1"
DATASET_PAYLOAD_NAME: Final[str] = "silver-jobs.jsonl"
DATASET_MANIFEST_NAME: Final[str] = "dataset-manifest.json"
SNAPSHOT_METADATA_NAME: Final[str] = "snapshot-metadata.json"
PACKAGE_MANIFEST_NAME: Final[str] = "package-manifest.json"
CPU_VALIDATION_REPORT_NAME: Final[str] = "cpu-validation-report.json"
UNSPLIT_EVIDENCE_STRATEGY: Final[str] = "unsplit_evidence_snapshot_v1"
UNLABELED_EVIDENCE_PROVENANCE: Final[str] = "none:unlabeled_evidence_snapshot_v1"


@dataclass(frozen=True)
class SnapshotMaterializationSpec:
    feature_contract_version: str
    product_contract_version: str
    code_commit: str


@dataclass(frozen=True)
class MaterializedTrainingPackage:
    package_manifest: TrainingPackageManifest
    dataset_manifest: TrainingDatasetManifest
    snapshot_metadata: Mapping[str, Any]
    contents: Mapping[str, bytes]
    cpu_validation: CpuValidationReport


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _normalize_cutoff(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("evidence_cutoff must be timezone-aware.")
    return value.astimezone(UTC)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("snapshot datetime values must be timezone-aware.")
        return _iso_utc(value)
    if isinstance(value, date):
        return value.isoformat()
    raise ValueError(
        "snapshot rows contain an unsupported value type "
        f"{type(value).__name__!r}."
    )


def _validate_spec(spec: SnapshotMaterializationSpec) -> None:
    for field_name, value in {
        "feature_contract_version": spec.feature_contract_version,
        "product_contract_version": spec.product_contract_version,
        "code_commit": spec.code_commit,
    }.items():
        if not value.strip():
            raise ValueError(f"{field_name} must be non-empty.")


def _normalize_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    plan: TrainingSnapshotPlan,
    evidence_cutoff: datetime,
) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError("read-only Silver snapshot returned no rows.")

    expected_names = snapshot_column_names(plan)
    expected_set = set(expected_names)
    cutoff = _normalize_cutoff(evidence_cutoff)
    normalized_rows: list[dict[str, Any]] = []
    seen_primary_keys: set[int] = set()

    for raw in rows:
        actual_set = set(raw)
        if actual_set != expected_set:
            missing = sorted(expected_set - actual_set)
            extra = sorted(actual_set - expected_set)
            raise ValueError(
                "snapshot row fields mismatch; "
                f"missing={missing}, extra={extra}."
            )

        primary_key_value = raw[plan.primary_key]
        if (
            isinstance(primary_key_value, bool)
            or not isinstance(primary_key_value, int)
            or primary_key_value <= 0
        ):
            raise ValueError("snapshot primary keys must be positive integers.")
        if primary_key_value in seen_primary_keys:
            raise ValueError(f"duplicate snapshot primary key {primary_key_value!r}.")
        seen_primary_keys.add(primary_key_value)

        for timestamp_name in ("normalized_at", "created_at", "updated_at"):
            timestamp = raw[timestamp_name]
            if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
                raise ValueError(f"{timestamp_name} must be a timezone-aware datetime.")
            if timestamp.astimezone(UTC) > cutoff:
                raise ValueError(
                    f"snapshot row {primary_key_value} crossed evidence cutoff "
                    f"through {timestamp_name}."
                )

        normalized_rows.append(
            {name: _canonical_value(raw[name]) for name in expected_names}
        )

    normalized_rows.sort(key=lambda row: row[plan.primary_key])
    return normalized_rows


def serialize_dataset_payload(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(f"{_canonical_json(dict(row))}\n" for row in rows).encode("utf-8")


def _snapshot_identity_core(
    *,
    plan: TrainingSnapshotPlan,
    evidence_cutoff: datetime,
    payload_fingerprint: str,
    row_count: int,
) -> dict[str, Any]:
    snapshot_sql = build_training_snapshot_sql(plan)
    preamble = read_only_transaction_preamble(plan)
    return {
        "schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "source_relation": plan.source_relation,
        "evidence_cutoff_utc": _iso_utc(_normalize_cutoff(evidence_cutoff)),
        "row_count": row_count,
        "snapshot_plan_fingerprint": fingerprint_training_snapshot_plan(plan),
        "query_fingerprint": fingerprint_bytes(snapshot_sql.encode("utf-8")),
        "transaction_preamble_fingerprint": fingerprint_bytes(preamble.encode("utf-8")),
        "dataset_payload_fingerprint": payload_fingerprint,
        "read_only": True,
        "isolation_level": plan.isolation_level,
    }


def _source_snapshot_id(identity_core: Mapping[str, Any]) -> str:
    digest = sha256(_canonical_json(dict(identity_core)).encode("utf-8")).hexdigest()
    return f"{SNAPSHOT_SOURCE_RELATION}:sha256:{digest}"


def _dataset_version(source_snapshot: str) -> str:
    digest = source_snapshot.rsplit(":", 1)[-1]
    return f"silver-jobs-{digest[:16]}"


def _package_id(
    *,
    dataset_manifest_fingerprint: str,
    snapshot_plan_fingerprint: str,
    source_snapshot: str,
    feature_contract_version: str,
    product_contract_version: str,
    code_commit: str,
    entries: Sequence[Any],
) -> str:
    core = {
        "dataset_manifest_fingerprint": dataset_manifest_fingerprint,
        "snapshot_plan_fingerprint": snapshot_plan_fingerprint,
        "source_snapshot": source_snapshot,
        "feature_contract_version": feature_contract_version,
        "product_contract_version": product_contract_version,
        "code_commit": code_commit,
        "entries": [asdict(entry) for entry in entries],
    }
    digest = sha256(_canonical_json(core).encode("utf-8")).hexdigest()
    return f"mfl005-{digest[:20]}"


def _aggregate_snapshot_metadata(
    rows: Sequence[Mapping[str, Any]],
    plan: TrainingSnapshotPlan,
) -> dict[str, Any]:
    source_counts = Counter(str(row["source_name"]) for row in rows)
    feature_names = [
        column.name
        for column in plan.selected_columns
        if column.role == "feature_candidate"
    ]
    null_counts = {
        name: sum(row[name] is None for row in rows)
        for name in feature_names
    }
    canonical_group_count = sum(
        bool(str(row[plan.grouping.primary_group_key] or "").strip())
        for row in rows
    )
    return {
        "source_name_counts": dict(sorted(source_counts.items())),
        "feature_null_counts": null_counts,
        "canonical_group_key_present_count": canonical_group_count,
        "fallback_group_required_count": len(rows) - canonical_group_count,
    }


def materialize_training_package_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    evidence_cutoff: datetime,
    spec: SnapshotMaterializationSpec,
    plan: TrainingSnapshotPlan | None = None,
) -> MaterializedTrainingPackage:
    _validate_spec(spec)
    selected_plan = plan or default_training_snapshot_plan()
    cutoff = _normalize_cutoff(evidence_cutoff)
    normalized_rows = _normalize_rows(
        rows,
        plan=selected_plan,
        evidence_cutoff=cutoff,
    )

    dataset_payload = serialize_dataset_payload(normalized_rows)
    payload_fingerprint = fingerprint_bytes(dataset_payload)
    identity_core = _snapshot_identity_core(
        plan=selected_plan,
        evidence_cutoff=cutoff,
        payload_fingerprint=payload_fingerprint,
        row_count=len(normalized_rows),
    )
    source_snapshot = _source_snapshot_id(identity_core)

    dataset_contract = TrainingDatasetContract(
        dataset_version=_dataset_version(source_snapshot),
        feature_contract_version=spec.feature_contract_version,
        product_contract_version=spec.product_contract_version,
        source_snapshot=source_snapshot,
        code_commit=spec.code_commit,
        split_strategy=UNSPLIT_EVIDENCE_STRATEGY,
        label_provenance=UNLABELED_EVIDENCE_PROVENANCE,
    )
    dataset_manifest = TrainingDatasetManifest(contract=dataset_contract)
    dataset_manifest_bytes = (
        serialize_training_dataset_manifest(dataset_manifest) + "\n"
    ).encode("utf-8")
    dataset_manifest_fingerprint = fingerprint_training_dataset_manifest(dataset_manifest)
    snapshot_plan_fingerprint = fingerprint_training_snapshot_plan(selected_plan)

    primary_keys = [row[selected_plan.primary_key] for row in normalized_rows]
    snapshot_metadata = {
        **identity_core,
        **_aggregate_snapshot_metadata(normalized_rows, selected_plan),
        "source_snapshot": source_snapshot,
        "dataset_version": dataset_contract.dataset_version,
        "dataset_manifest_fingerprint": dataset_manifest_fingerprint,
        "feature_contract_version": spec.feature_contract_version,
        "product_contract_version": spec.product_contract_version,
        "code_commit": spec.code_commit,
        "selected_columns": [
            {"name": column.name, "role": column.role}
            for column in selected_plan.selected_columns
        ],
        "primary_key": selected_plan.primary_key,
        "first_primary_key": primary_keys[0],
        "last_primary_key": primary_keys[-1],
        "split_strategy": UNSPLIT_EVIDENCE_STRATEGY,
        "label_provenance": UNLABELED_EVIDENCE_PROVENANCE,
        "external_execution": False,
        "product_authority": False,
    }
    snapshot_metadata_bytes = (
        _canonical_json(snapshot_metadata) + "\n"
    ).encode("utf-8")

    contents = {
        DATASET_PAYLOAD_NAME: dataset_payload,
        DATASET_MANIFEST_NAME: dataset_manifest_bytes,
        SNAPSHOT_METADATA_NAME: snapshot_metadata_bytes,
    }
    entries = (
        build_training_package_entry(
            role="dataset_payload",
            name=DATASET_PAYLOAD_NAME,
            content=dataset_payload,
        ),
        build_training_package_entry(
            role="dataset_manifest",
            name=DATASET_MANIFEST_NAME,
            content=dataset_manifest_bytes,
        ),
        build_training_package_entry(
            role="snapshot_metadata",
            name=SNAPSHOT_METADATA_NAME,
            content=snapshot_metadata_bytes,
        ),
    )
    manifest = TrainingPackageManifest(
        package_id=_package_id(
            dataset_manifest_fingerprint=dataset_manifest_fingerprint,
            snapshot_plan_fingerprint=snapshot_plan_fingerprint,
            source_snapshot=source_snapshot,
            feature_contract_version=spec.feature_contract_version,
            product_contract_version=spec.product_contract_version,
            code_commit=spec.code_commit,
            entries=entries,
        ),
        dataset_manifest_fingerprint=dataset_manifest_fingerprint,
        snapshot_plan_fingerprint=snapshot_plan_fingerprint,
        source_snapshot=source_snapshot,
        feature_contract_version=spec.feature_contract_version,
        product_contract_version=spec.product_contract_version,
        code_commit=spec.code_commit,
        entries=entries,
    )
    cpu_validation = validate_training_package_contents(manifest, contents)
    return MaterializedTrainingPackage(
        package_manifest=manifest,
        dataset_manifest=dataset_manifest,
        snapshot_metadata=snapshot_metadata,
        contents=contents,
        cpu_validation=cpu_validation,
    )


def _read_setting_value(row: Any) -> str:
    if isinstance(row, Mapping):
        if len(row) != 1:
            raise ValueError("database setting probe returned an unexpected mapping.")
        return str(next(iter(row.values())))
    if isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
        if len(row) != 1:
            raise ValueError("database setting probe returned an unexpected sequence.")
        return str(row[0])
    raise ValueError("database setting probe returned an unsupported row shape.")


def load_read_only_snapshot_rows(
    connection: Any,
    *,
    evidence_cutoff: datetime,
    plan: TrainingSnapshotPlan | None = None,
) -> list[Mapping[str, Any]]:
    selected_plan = plan or default_training_snapshot_plan()
    cutoff = _normalize_cutoff(evidence_cutoff)
    preamble = read_only_transaction_preamble(selected_plan)
    sql = build_training_snapshot_sql(selected_plan)

    try:
        with connection.cursor() as cursor:
            cursor.execute(preamble)
            cursor.execute("SHOW transaction_read_only;")
            read_only_setting = _read_setting_value(cursor.fetchone()).strip().lower()
            if read_only_setting not in {"on", "true"}:
                raise RuntimeError("database transaction did not enter read-only mode.")

            cursor.execute("SHOW transaction_isolation;")
            isolation_setting = _read_setting_value(cursor.fetchone()).strip().lower()
            expected_isolation = SNAPSHOT_ISOLATION_LEVEL.lower()
            if isolation_setting != expected_isolation:
                raise RuntimeError(
                    "database transaction isolation drifted; "
                    f"expected {expected_isolation!r}, got {isolation_setting!r}."
                )

            cursor.execute(sql, {selected_plan.cutoff_parameter: cutoff})
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.rollback()


def materialize_training_package_from_database(
    connection: Any,
    *,
    evidence_cutoff: datetime,
    spec: SnapshotMaterializationSpec,
    plan: TrainingSnapshotPlan | None = None,
) -> MaterializedTrainingPackage:
    selected_plan = plan or default_training_snapshot_plan()
    rows = load_read_only_snapshot_rows(
        connection,
        evidence_cutoff=evidence_cutoff,
        plan=selected_plan,
    )
    return materialize_training_package_from_rows(
        rows,
        evidence_cutoff=evidence_cutoff,
        spec=spec,
        plan=selected_plan,
    )


def _cpu_validation_payload(report: CpuValidationReport) -> dict[str, Any]:
    return {
        **asdict(report),
        "schema_version": "ml-cpu-validation-report/v1",
    }


def validate_written_training_package(
    package_dir: Path,
    manifest: TrainingPackageManifest,
) -> CpuValidationReport:
    expected_names = {entry.name for entry in manifest.entries}
    contents = {
        name: (package_dir / name).read_bytes()
        for name in sorted(expected_names)
    }
    report = validate_training_package_contents(manifest, contents)
    expected_fingerprint = fingerprint_training_package_manifest(manifest)
    if report.package_fingerprint != expected_fingerprint:
        raise ValueError("written package fingerprint changed after validation.")
    return report


def write_materialized_training_package(
    package: MaterializedTrainingPackage,
    *,
    output_root: Path,
) -> Path:
    validate_training_package_contents(package.package_manifest, package.contents)
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / package.package_manifest.package_id
    if target.exists():
        raise FileExistsError(f"immutable training package already exists: {target}")

    temporary = output_root / f".{package.package_manifest.package_id}.tmp"
    if temporary.exists():
        raise FileExistsError(f"stale materialization staging directory exists: {temporary}")
    temporary.mkdir()

    try:
        for name, content in package.contents.items():
            (temporary / name).write_bytes(content)

        (temporary / PACKAGE_MANIFEST_NAME).write_text(
            serialize_training_package_manifest(package.package_manifest) + "\n",
            encoding="utf-8",
        )
        disk_validation = validate_written_training_package(
            temporary,
            package.package_manifest,
        )
        (temporary / CPU_VALIDATION_REPORT_NAME).write_text(
            _canonical_json(_cpu_validation_payload(disk_validation)) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return target
