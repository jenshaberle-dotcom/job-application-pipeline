from pathlib import Path

import pytest

from scripts.review_finanz_informatik_activation_gate import (
    candidate_from_raw_record,
    run_activation_gate,
)
from scripts.review_finanz_informatik_incremental_uniqueness import EvidenceRecord
from src.connectors.base import RawJobRecord


class FakeConnector:
    def __init__(self, records: list[RawJobRecord]) -> None:
        self.records = records

    def fetch_jobs(self, profile, search_term):
        return self.records, "https://www.f-i.de/de/karriere/offene-stellen"


def raw_record(title: str, url: str, profile_terms: list[str]) -> RawJobRecord:
    return RawJobRecord(
        source_name="finanz_informatik:hannover",
        source_url=url,
        external_job_id=title.lower().replace(" ", "-"),
        raw_data={
            "job": {
                "title": title,
                "company_name": "Finanz Informatik GmbH & Co. KG",
                "location": "hannover",
                "source_url": url,
                "profile_terms": profile_terms,
            },
            "result_card": {
                "title": title,
                "company_name": "Finanz Informatik GmbH & Co. KG",
                "location": "hannover",
                "detail_url": url,
            },
        },
    )


def test_candidate_from_raw_record_uses_connector_evidence() -> None:
    record = raw_record(
        "Product Owner OSPlus Versiegelung",
        "https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d",
        ["product owner", "sql"],
    )

    candidate = candidate_from_raw_record(record)

    assert candidate.source_candidate_url == record.source_url
    assert candidate.page_title == "Product Owner OSPlus Versiegelung"
    assert candidate.recommendation == "connector_candidate_record"
    assert candidate.matched_profile_terms == "product owner; sql"
    assert candidate.matched_location_terms == "hannover"


def test_run_activation_gate_uses_connector_records_and_database_evidence(tmp_path: Path) -> None:
    records = [
        raw_record(
            "JavaScript und UI Entwickler",
            "https://www.f-i.de/de/karriere/offene-stellen/hannover/java-script-und-ui-entwickler-m-w-d",
            ["javascript", "ui"],
        ),
        raw_record(
            "Product Owner OSPlus Versiegelung",
            "https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d",
            ["product owner", "sql"],
        ),
    ]

    evidence = [
        EvidenceRecord(
            table_name="raw_jobs",
            record_id="7973",
            source_name="stepstone",
            source_url="https://example.test/stepstone/javascript-ui",
            title="JavaScript und UI Entwickler",
            company_name="Finanz Informatik GmbH & Co. KG",
            location="Hannover",
            evidence_text="JavaScript und UI Entwickler Finanz Informatik Hannover",
        )
    ]

    manifest = run_activation_gate(
        export_dir=tmp_path,
        dsn=None,
        connector=FakeConnector(records),
        evidence_override=evidence,
    )

    assert manifest["input_source"] == "live_finanz_informatik_connector_candidate_preview_and_current_database_evidence"
    assert manifest["database_writes"] is False
    assert manifest["bronze_persistence_approved"] is False
    assert manifest["connector_registered_for_ingestion"] is False
    assert manifest["candidate_count"] == 2
    assert (tmp_path / "finanz_informatik_activation_gate_review.md").exists()
    assert (tmp_path / "finanz_informatik_activation_gate_manifest.json").exists()


def test_run_activation_gate_fails_when_database_evidence_is_unavailable(tmp_path: Path) -> None:
    records = [
        raw_record(
            "Product Owner OSPlus Versiegelung",
            "https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d",
            ["product owner"],
        )
    ]

    with pytest.raises(RuntimeError, match="requires current database evidence"):
        run_activation_gate(
            export_dir=tmp_path,
            dsn=None,
            connector=FakeConnector(records),
            evidence_override=[],
            db_error_override="No DSN configured",
        )
