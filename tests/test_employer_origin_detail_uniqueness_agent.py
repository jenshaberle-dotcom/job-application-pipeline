from __future__ import annotations

from pathlib import Path

from scripts.run_employer_origin_detail_uniqueness_agent import (
    DetailCandidate,
    ExistingEvidence,
    detail_evidence_outcome,
    incremental_uniqueness_outcome,
    title_similarity,
    url_slug_title,
)


def test_url_slug_title_converts_job_url_to_title_hint() -> None:
    assert url_slug_title("https://example.com/jobs/product-owner-data-platform") == "product owner data platform"


def test_title_similarity_detects_close_titles() -> None:
    assert title_similarity("Product Owner Data Platform", "Product Owner Data Platform") == 1.0
    assert title_similarity("Product Owner Data Platform", "Java Developer") < 0.5


def test_detail_evidence_passes_when_profile_and_location_are_present() -> None:
    details = [
        DetailCandidate(
            url="https://example.com/jobs/product-owner",
            title="Product Owner",
            status_code=200,
            response_bytes=1000,
            profile_hits=("product owner",),
            location_hits=("hannover",),
            remote_hits=(),
            text_sample="Product Owner Hannover",
        )
    ]

    outcome = detail_evidence_outcome(details)

    assert outcome.gate_name == "detail_evidence_gate"
    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"


def test_detail_evidence_requires_profile_and_location_or_remote() -> None:
    details = [
        DetailCandidate(
            url="https://example.com/jobs/unknown",
            title="Unknown",
            status_code=200,
            response_bytes=1000,
            profile_hits=(),
            location_hits=("hannover",),
            remote_hits=(),
            text_sample="Hannover",
        )
    ]

    outcome = detail_evidence_outcome(details)

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"


def test_incremental_uniqueness_passes_with_unique_candidate() -> None:
    details = [
        DetailCandidate(
            url="https://example.com/jobs/product-owner",
            title="Product Owner Data Platform",
            status_code=200,
            response_bytes=1000,
            profile_hits=("product owner",),
            location_hits=("hannover",),
            remote_hits=(),
            text_sample="Product Owner Data Platform Hannover",
        )
    ]
    existing = [
        ExistingEvidence(
            table_name="silver_jobs",
            record_id=1,
            source_name="bundesagentur_fuer_arbeit",
            title="Java Developer",
            company_name="Other Company",
            location="Braunschweig",
            source_url="ba://example",
            evidence_text="Java Developer Braunschweig",
        )
    ]

    outcome = incremental_uniqueness_outcome(details, existing)

    assert outcome.gate_name == "incremental_uniqueness_gate"
    assert outcome.gate_status == "passed"
    assert outcome.decision == "passed"
    assert outcome.evidence["uniqueness_counts"]["incrementally_unique_candidate"] == 1


def test_incremental_uniqueness_requires_manual_review_for_close_match() -> None:
    details = [
        DetailCandidate(
            url="https://example.com/jobs/product-owner",
            title="Product Owner Data Platform",
            status_code=200,
            response_bytes=1000,
            profile_hits=("product owner",),
            location_hits=("hannover",),
            remote_hits=(),
            text_sample="Product Owner Data Platform Hannover",
        )
    ]
    existing = [
        ExistingEvidence(
            table_name="raw_jobs",
            record_id=10,
            source_name="stepstone",
            title="Product Owner Data Platform",
            company_name="Example AG",
            location="Hannover",
            source_url="https://stepstone.example/product-owner",
            evidence_text="Product Owner Data Platform Example AG Hannover",
        )
    ]

    outcome = incremental_uniqueness_outcome(details, existing)

    assert outcome.gate_status == "manual_review_required"
    assert outcome.decision == "manual_review_required"

def test_row_value_supports_tuple_and_dict_row_shapes() -> None:
    from scripts.run_employer_origin_detail_uniqueness_agent import row_value

    assert row_value((42, "passed"), "id", 0) == 42
    assert row_value((42, "passed"), "gate_status", 1) == "passed"
    assert row_value({"id": 42, "gate_status": "passed"}, "id", 0) == 42
    assert row_value({"id": 42, "gate_status": "passed"}, "gate_status", 1) == "passed"


def test_s2t_agent_has_no_tuple_only_or_global_dict_row_access() -> None:
    source = Path("scripts/run_employer_origin_detail_uniqueness_agent.py").read_text(encoding="utf-8")

    assert "previous[0]" not in source
    assert "previous[1]" not in source
    assert "previous[2]" not in source
    assert "previous[3]" not in source
    assert "previous[4]" not in source
    assert "cur.fetchone()[0]" not in source
    assert "psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row)" not in source

