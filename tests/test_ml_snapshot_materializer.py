from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import json
from typing import Any

import pytest

from src.search_intelligence.ml_experiment_transport import (
    fingerprint_training_package_manifest,
    validate_training_package_contents,
)
from src.search_intelligence.ml_snapshot_materializer import (
    CPU_VALIDATION_REPORT_NAME,
    DATASET_MANIFEST_NAME,
    DATASET_PAYLOAD_NAME,
    PACKAGE_MANIFEST_NAME,
    SNAPSHOT_METADATA_NAME,
    SnapshotMaterializationSpec,
    load_read_only_snapshot_rows,
    materialize_training_package_from_database,
    materialize_training_package_from_rows,
    validate_written_training_package,
    write_materialized_training_package,
)
from src.search_intelligence.ml_snapshot_plan import (
    build_training_snapshot_sql,
    default_training_snapshot_plan,
    read_only_transaction_preamble,
)


CUTOFF = datetime(2026, 8, 23, 16, 0, tzinfo=UTC)


def _row(
    row_id: int,
    *,
    title: str | None = "Machine Learning Engineer",
    source_name: str = "example_source",
    canonical_key_candidate: str | None = "example|ml-engineer|hannover",
) -> dict[str, Any]:
    timestamp = CUTOFF - timedelta(hours=1)
    return {
        "id": row_id,
        "raw_job_id": 1000 + row_id,
        "source_name": source_name,
        "external_job_id": f"job-{row_id}",
        "source_url": f"https://example.test/jobs/{row_id}",
        "title": title,
        "company_name": "Example GmbH",
        "city": "Hannover",
        "postal_code": "30159",
        "country": "DE",
        "publication_date": date(2026, 8, 22),
        "normalized_title": "machine learning engineer",
        "normalized_company_name": "example gmbh",
        "normalized_location": "hannover de",
        "canonical_status": "canonical",
        "canonical_source_type": "employer_origin",
        "canonical_key_candidate": canonical_key_candidate,
        "normalized_at": timestamp,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def _spec() -> SnapshotMaterializationSpec:
    return SnapshotMaterializationSpec(
        feature_contract_version="ml-training-snapshot-plan/v1:sha256:" + "1" * 64,
        product_contract_version="prd:sha256:" + "2" * 64,
        code_commit="3" * 40,
    )


class _FakeCursor:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        read_only: str = "on",
        isolation: str = "repeatable read",
    ) -> None:
        self.rows = rows
        self.read_only = read_only
        self.isolation = isolation
        self.executed: list[tuple[str, dict[str, Any] | None]] = []
        self._one: tuple[str] | None = None
        self._selected = False

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        return None

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        self.executed.append((sql, params))
        normalized = sql.strip().lower()
        if normalized == "show transaction_read_only;":
            self._one = (self.read_only,)
            self._selected = False
        elif normalized == "show transaction_isolation;":
            self._one = (self.isolation,)
            self._selected = False
        elif normalized.startswith("select"):
            self._one = None
            self._selected = True
        else:
            self._one = None
            self._selected = False

    def fetchone(self) -> tuple[str] | None:
        return self._one

    def fetchall(self) -> list[dict[str, Any]]:
        if not self._selected:
            raise AssertionError("fetchall called without the snapshot SELECT")
        return self.rows


class _FakeConnection:
    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        read_only: str = "on",
        isolation: str = "repeatable read",
    ) -> None:
        self.cursor_instance = _FakeCursor(
            rows,
            read_only=read_only,
            isolation=isolation,
        )
        self.rollback_count = 0

    def cursor(self) -> _FakeCursor:
        return self.cursor_instance

    def rollback(self) -> None:
        self.rollback_count += 1


def test_materialization_is_deterministic_and_orders_by_primary_key() -> None:
    first = materialize_training_package_from_rows(
        [_row(2), _row(1)],
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )
    second = materialize_training_package_from_rows(
        [_row(1), _row(2)],
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )

    assert first.package_manifest == second.package_manifest
    assert first.contents == second.contents
    assert first.cpu_validation == second.cpu_validation
    assert first.snapshot_metadata["row_count"] == 2
    assert first.snapshot_metadata["first_primary_key"] == 1
    assert first.snapshot_metadata["last_primary_key"] == 2

    payload_lines = first.contents[DATASET_PAYLOAD_NAME].decode("utf-8").splitlines()
    assert [json.loads(line)["id"] for line in payload_lines] == [1, 2]
    assert json.loads(payload_lines[0])["publication_date"] == "2026-08-22"
    assert json.loads(payload_lines[0])["updated_at"].endswith("Z")


def test_source_snapshot_changes_when_cutoff_or_payload_changes() -> None:
    baseline = materialize_training_package_from_rows(
        [_row(1)],
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )
    later_cutoff = materialize_training_package_from_rows(
        [_row(1)],
        evidence_cutoff=CUTOFF + timedelta(minutes=1),
        spec=_spec(),
    )
    changed_payload = materialize_training_package_from_rows(
        [_row(1, title="Senior Machine Learning Engineer")],
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )

    assert baseline.package_manifest.source_snapshot != later_cutoff.package_manifest.source_snapshot
    assert baseline.package_manifest.source_snapshot != changed_payload.package_manifest.source_snapshot


def test_snapshot_metadata_keeps_only_aggregate_diagnostics() -> None:
    package = materialize_training_package_from_rows(
        [
            _row(1, source_name="source_b"),
            _row(2, source_name="source_a", canonical_key_candidate=None),
            _row(3, source_name="source_a", title=None),
        ],
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )

    assert package.snapshot_metadata["source_name_counts"] == {
        "source_a": 2,
        "source_b": 1,
    }
    assert package.snapshot_metadata["feature_null_counts"]["title"] == 1
    assert package.snapshot_metadata["canonical_group_key_present_count"] == 2
    assert package.snapshot_metadata["fallback_group_required_count"] == 1
    assert package.snapshot_metadata["external_execution"] is False
    assert package.snapshot_metadata["product_authority"] is False
    assert package.dataset_manifest.contract.label_provenance == (
        "none:unlabeled_evidence_snapshot_v1"
    )
    assert package.dataset_manifest.contract.split_strategy == "unsplit_evidence_snapshot_v1"


def test_materialization_fails_closed_on_empty_or_schema_drift() -> None:
    with pytest.raises(ValueError, match="returned no rows"):
        materialize_training_package_from_rows(
            [],
            evidence_cutoff=CUTOFF,
            spec=_spec(),
        )

    row = _row(1)
    row.pop("source_name")
    with pytest.raises(ValueError, match="fields mismatch"):
        materialize_training_package_from_rows(
            [row],
            evidence_cutoff=CUTOFF,
            spec=_spec(),
        )


def test_materialization_rechecks_evidence_cutoff_in_python() -> None:
    row = _row(1)
    row["updated_at"] = CUTOFF + timedelta(seconds=1)

    with pytest.raises(ValueError, match="crossed evidence cutoff"):
        materialize_training_package_from_rows(
            [row],
            evidence_cutoff=CUTOFF,
            spec=_spec(),
        )


def test_read_only_loader_proves_transaction_boundary_and_rolls_back() -> None:
    connection = _FakeConnection([_row(1)])
    plan = default_training_snapshot_plan()

    rows = load_read_only_snapshot_rows(
        connection,
        evidence_cutoff=CUTOFF,
        plan=plan,
    )

    assert rows == [_row(1)]
    assert connection.rollback_count == 1
    executed = connection.cursor_instance.executed
    assert executed[0] == (read_only_transaction_preamble(plan), None)
    assert executed[1] == ("SHOW transaction_read_only;", None)
    assert executed[2] == ("SHOW transaction_isolation;", None)
    assert executed[3][0] == build_training_snapshot_sql(plan)
    assert executed[3][1] == {"evidence_cutoff": CUTOFF}


def test_read_only_loader_fails_if_database_did_not_enter_read_only_mode() -> None:
    connection = _FakeConnection([_row(1)], read_only="off")

    with pytest.raises(RuntimeError, match="did not enter read-only mode"):
        load_read_only_snapshot_rows(
            connection,
            evidence_cutoff=CUTOFF,
        )

    assert connection.rollback_count == 1
    assert not any(
        sql.strip().lower().startswith("select")
        for sql, _ in connection.cursor_instance.executed
    )


def test_read_only_loader_fails_if_isolation_drifted() -> None:
    connection = _FakeConnection([_row(1)], isolation="read committed")

    with pytest.raises(RuntimeError, match="isolation drifted"):
        load_read_only_snapshot_rows(
            connection,
            evidence_cutoff=CUTOFF,
        )

    assert connection.rollback_count == 1


def test_database_materialization_reuses_same_package_builder() -> None:
    connection = _FakeConnection([_row(2), _row(1)])

    from_database = materialize_training_package_from_database(
        connection,
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )
    from_rows = materialize_training_package_from_rows(
        [_row(2), _row(1)],
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )

    assert from_database.package_manifest == from_rows.package_manifest
    assert from_database.contents == from_rows.contents
    assert connection.rollback_count == 1


def test_package_content_tampering_is_rejected() -> None:
    package = materialize_training_package_from_rows(
        [_row(1)],
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )
    tampered = dict(package.contents)
    tampered[DATASET_PAYLOAD_NAME] += b"tamper"

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        validate_training_package_contents(package.package_manifest, tampered)


def test_write_validates_staging_bytes_before_immutable_publish(tmp_path) -> None:
    package = materialize_training_package_from_rows(
        [_row(1), _row(2)],
        evidence_cutoff=CUTOFF,
        spec=_spec(),
    )

    target = write_materialized_training_package(
        package,
        output_root=tmp_path,
    )

    assert target == tmp_path / package.package_manifest.package_id
    assert {
        DATASET_PAYLOAD_NAME,
        DATASET_MANIFEST_NAME,
        SNAPSHOT_METADATA_NAME,
        PACKAGE_MANIFEST_NAME,
        CPU_VALIDATION_REPORT_NAME,
    } <= {path.name for path in target.iterdir()}
    report = validate_written_training_package(target, package.package_manifest)
    assert report.package_fingerprint == fingerprint_training_package_manifest(
        package.package_manifest
    )

    with pytest.raises(FileExistsError, match="immutable training package already exists"):
        write_materialized_training_package(
            package,
            output_root=tmp_path,
        )
