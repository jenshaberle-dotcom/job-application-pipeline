from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.export_jap_cloud_vnext_recycle import (
    MANIFEST_SCHEMA,
    RECYCLE_CONTRACT_VERSION,
    _candidate_evidence_index,
    build_candidate_artifacts,
    build_fact_artifacts,
    build_source_artifacts,
    build_vacancy_artifacts,
    write_export_bundle,
)


def test_candidate_export_requires_reconstructed_real_job_evidence() -> None:
    candidates = [
        {
            "id": 1,
            "company_key": "alpha",
            "company_name": "Alpha GmbH",
            "source_name_candidate": "stepstone",
            "status": "discovery",
            "created_at": "2026-09-01T10:00:00+00:00",
        },
        {
            "id": 2,
            "company_key": "beta",
            "company_name": "Beta GmbH",
            "source_name_candidate": "candidate:beta",
            "status": "candidate",
            "created_at": "2026-09-02T10:00:00+00:00",
        },
    ]
    evidence = _candidate_evidence_index(
        market_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 10,
                "source_name": "stepstone",
                "title": "Data Engineer",
                "evidence_url": "https://example.test/job/1",
                "evidence": {"job": True},
                "observed_at": "2026-09-01T09:00:00+00:00",
            }
        ]
    )
    companies, exported, gaps = build_candidate_artifacts(
        candidates=candidates,
        evidence_index=evidence,
        classic_sha="a" * 40,
    )

    assert [row["company_key"] for row in companies] == ["alpha"]
    assert [row["company_key"] for row in exported] == ["alpha"]
    assert exported[0]["admission_reason"] == "REAL_JOB_OBSERVED"
    assert exported[0]["admission_evidence"]["sensor_key"] == "stepstone"
    assert exported[0]["admission_evidence"]["sensor_identity_boundary"] == (
        "DISCOVERY_PROVENANCE_ONLY"
    )
    assert gaps == [
        {
            "candidate_id": 2,
            "company_key": "beta",
            "company_name": "Beta GmbH",
            "gap": "REAL_JOB_OBSERVED_PROVENANCE_NOT_RECONSTRUCTED",
            "classic_status": "candidate",
            "source_name_candidate": "candidate:beta",
        }
    ]


def test_evidence_precedence_prefers_candidate_promotion_over_market_or_silver() -> None:
    evidence = _candidate_evidence_index(
        promotion_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 1,
                "source_name": "stepstone",
                "evidence_count": 2,
                "evidence": {
                    "sample_titles": ["Data Engineer"],
                    "source_name": "stepstone",
                },
                "latest_job_observed_at": "2026-08-31T08:00:00+00:00",
                "created_at": "2026-09-01T08:00:00+00:00",
            }
        ],
        market_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 2,
                "source_name": "stepstone",
                "title": "Job",
                "evidence_url": "https://example.test/job",
                "evidence": {},
                "observed_at": "2026-09-01T07:00:00+00:00",
            }
        ],
        silver_rows=[
            {
                "candidate_id": 1,
                "silver_job_id": 3,
                "source_name": "generic_origin:alpha",
                "title": "Job",
                "source_url": "https://alpha.test/job",
                "updated_at": "2026-09-01T09:00:00+00:00",
            }
        ],
    )
    assert evidence[1]["origin_kind"] == "CANDIDATE_PROMOTION_JOB_EVIDENCE"
    assert evidence[1]["classic_row_id"] == 1
    assert evidence[1]["observed_job_titles"] == ["Data Engineer"]
    assert evidence[1]["observed_at"] == "2026-08-31T08:00:00+00:00"


def test_active_source_export_is_generic_and_fingerprint_is_deterministic() -> None:
    rows = [
        {
            "candidate_id": 7,
            "company_key": "alpha",
            "source_name": "generic_origin:alpha",
            "origin_url": "https://jobs.alpha.test",
            "authority": "generic_evidence_driven_layer_model",
            "proof_state": "pass",
            "proof_evidence": {"layer": "proof", "state": "pass"},
            "source_type_candidate": "employer_origin_ats_backed_career_site",
            "activated_at": "2026-09-01T00:00:00+00:00",
            "updated_at": "2026-09-02T00:00:00+00:00",
        }
    ]
    first = build_source_artifacts(rows, classic_sha="a" * 40)
    second = build_source_artifacts(rows, classic_sha="a" * 40)
    assert first == second
    assert first[0]["source_kind"] == "ATS_DELEGATED"
    assert first[0]["source_key"] == "generic_origin:alpha"
    assert len(first[0]["fingerprint_sha256"]) == 64


def test_current_vacancy_export_uses_gold_identity_and_source_identity() -> None:
    rows = [
        {
            "silver_job_id": 11,
            "raw_job_id": 21,
            "source_name": "generic_origin:alpha",
            "external_job_id": "ABC-123",
            "source_url": "https://jobs.alpha.test/job/ABC-123",
            "title": "Data Engineer",
            "company_name": "Alpha GmbH",
            "city": "Hannover",
            "country": "DE",
            "publication_date": "2026-09-29",
            "normalized_location": "hannover de",
            "company_key": "alpha",
            "canonical_vacancy_key": "origin-id|jobs.alpha.test|abc-123",
            "identity_kind": "strong_origin_identifier",
            "latest_seen_at": "2026-09-30T08:00:00+00:00",
            "exact_observed_origin_url": "https://jobs.alpha.test/job/ABC-123",
            "raw_data": {"title": "Data Engineer"},
            "content_hash": None,
            "raw_created_at": "2026-09-29T08:00:00+00:00",
            "silver_created_at": "2026-09-29T08:01:00+00:00",
            "silver_updated_at": "2026-09-30T08:01:00+00:00",
            "first_seen_at": "2026-09-29T08:00:00+00:00",
            "last_seen_at": "2026-09-30T08:00:00+00:00",
        }
    ]
    result = build_vacancy_artifacts(
        rows,
        locations_by_silver_id={
            11: [
                {
                    "city": "Hannover",
                    "country_code": "DE",
                    "is_primary": True,
                    "evidence_source": "structured",
                    "evidence_text": "Hannover",
                }
            ]
        },
        classic_sha="a" * 40,
    )
    row = result[0]
    assert row["source_vacancy_key"] == "generic_origin:alpha|external:ABC-123"
    assert row["canonical_identity_key"] == "origin-id|jobs.alpha.test|abc-123"
    assert row["availability_state"] == "OPEN"
    assert row["locations"][0]["city"] == "Hannover"
    assert len(row["content_sha256"]) == 64


def test_requirement_fact_export_reuses_evidence_hash_when_sha256() -> None:
    result = build_fact_artifacts(
        [
            {
                "silver_job_id": 11,
                "evidence_schema": "requirements.v1",
                "parser_family": "jsonld",
                "evidence_hash": "b" * 64,
                "evidence_payload": {"skills": ["Python"]},
                "updated_at": "2026-09-30T08:00:00+00:00",
            }
        ],
        source_vacancy_key_by_silver_id={11: "generic_origin:alpha|external:ABC-123"},
    )
    assert result[0]["fact_kind"] == "requirements"
    assert result[0]["evidence_sha256"] == "b" * 64
    assert result[0]["extractor_revision"] == "jsonld:requirements.v1"


def test_manifest_matches_cloud_contract_hash_shape(tmp_path: Path) -> None:
    manifest = write_export_bundle(
        tmp_path,
        classic_sha="a" * 40,
        companies=[{"company_key": "alpha", "canonical_name": "Alpha", "provenance": {}}],
        candidates=[
            {
                "company_key": "alpha",
                "admission_reason": "REAL_JOB_OBSERVED",
                "first_observed_at": "2026-09-01T00:00:00Z",
                "latest_evidence_at": "2026-09-01T00:00:00Z",
                "admission_evidence": {"origin_kind": "MARKET_JOB_EVIDENCE"},
            }
        ],
        sources=[],
        vacancies=[],
        facts=[],
        extracted_at="2026-09-30T10:00:00Z",
    )
    assert manifest["schema_version"] == MANIFEST_SCHEMA
    assert manifest["contract_version"] == RECYCLE_CONTRACT_VERSION
    assert [item["logical_name"] for item in manifest["artifacts"]] == [
        "companies",
        "employer_candidates",
        "employer_sources",
        "current_vacancies",
    ]
    unsigned = dict(manifest)
    claimed = unsigned.pop("manifest_sha256")
    observed = hashlib.sha256(
        (
            json.dumps(
                unsigned,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    assert claimed == observed


def test_promotion_without_job_title_does_not_claim_real_job_observed() -> None:
    evidence = _candidate_evidence_index(
        promotion_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 1,
                "source_name": "stepstone",
                "evidence_count": 4,
                "evidence": {
                    "search_terms": ["data engineer"],
                    "sample_titles": [],
                },
                "created_at": "2026-09-01T08:00:00+00:00",
            }
        ],
        market_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 2,
                "source_name": "stepstone",
                "title": "Data Engineer",
                "evidence_url": None,
                "evidence": {"market_sensor": True},
                "observed_at": "2026-08-31T08:00:00+00:00",
            }
        ],
    )
    assert evidence[1]["origin_kind"] == "MARKET_JOB_EVIDENCE"
    assert evidence[1]["title"] == "Data Engineer"
    assert evidence[1]["evidence_url"] is None


def test_market_job_title_is_sufficient_even_when_sensor_does_not_store_job_url() -> None:
    evidence = _candidate_evidence_index(
        market_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 10,
                "source_name": "stepstone",
                "title": "Analytics Engineer",
                "evidence_url": None,
                "evidence": {"evidence_kind": "market_sensor_company_sighting"},
                "source_seen_at": "2026-09-01T07:30:00+00:00",
                "observed_at": "2026-09-01T08:00:00+00:00",
            }
        ]
    )
    assert evidence[1]["origin_kind"] == "MARKET_JOB_EVIDENCE"
    assert evidence[1]["observed_at"] == "2026-09-01T07:30:00+00:00"


def test_real_manual_linkedin_observation_is_preserved_without_sensor_authority() -> None:
    evidence = _candidate_evidence_index(
        market_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 10,
                "evidence_kind": "manual_market_observation",
                "evidence_source": "manual_market_observation",
                "source_name": "linkedin",
                "title": "Data Engineer",
                "evidence_url": "https://www.linkedin.com/jobs/view/123",
                "evidence": {
                    "input_mode": "manual_market_observation",
                    "observation_origin": "external_market_observation",
                },
                "observed_at": "2026-09-01T08:00:00+00:00",
            }
        ]
    )
    row = evidence[1]
    assert row["origin_kind"] == "LEGACY_MANUAL_JOB_OBSERVATION"
    assert row["title"] == "Data Engineer"
    assert row["discovery_channel"] == "linkedin"
    assert row["sensor_key"] is None
    assert row["automatic_sensor_authority"] is False


def test_detail_evidence_requires_job_title_and_prefers_updated_timestamp() -> None:
    evidence = _candidate_evidence_index(
        detail_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 9,
                "source_url": "https://jobs.alpha.test/job/9",
                "page_title": "ML Engineer",
                "status_code": 200,
                "confidence": "0.9500",
                "evidence": {"kind": "detail"},
                "created_at": "2026-09-01T07:00:00+00:00",
                "updated_at": "2026-09-02T08:00:00+00:00",
            }
        ]
    )
    row = evidence[1]
    assert row["origin_kind"] == "EMPLOYER_ORIGIN_JOB_DETAIL_EVIDENCE"
    assert row["title"] == "ML Engineer"
    assert row["observed_at"] == "2026-09-02T08:00:00+00:00"

    missing_title = _candidate_evidence_index(
        detail_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 10,
                "source_url": "https://jobs.alpha.test/job/10",
                "page_title": None,
                "evidence": {},
                "updated_at": "2026-09-02T08:00:00+00:00",
            }
        ]
    )
    assert missing_title == {}


def test_non_catalog_job_observation_with_title_is_recycled_as_legacy_discovery() -> None:
    evidence = _candidate_evidence_index(
        market_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 11,
                "evidence_kind": "manual_aggregator_sighting",
                "evidence_source": "manual_market_observation",
                "source_name": "some_future_board",
                "title": "Platform Engineer",
                "evidence_url": None,
                "evidence": {"input_mode": "manual_market_evidence"},
                "observed_at": "2026-09-03T08:00:00+00:00",
            }
        ]
    )
    row = evidence[1]
    assert row["origin_kind"] == "LEGACY_MANUAL_JOB_OBSERVATION"
    assert row["sensor_key"] is None
    assert row["automatic_sensor_authority"] is False


def test_manual_observation_without_job_title_still_does_not_prove_candidate() -> None:
    evidence = _candidate_evidence_index(
        market_rows=[
            {
                "candidate_id": 1,
                "evidence_id": 12,
                "evidence_kind": "manual_market_observation",
                "evidence_source": "manual_market_observation",
                "source_name": "linkedin",
                "title": "",
                "evidence_url": "https://www.linkedin.com/company/example",
                "evidence": {"input_mode": "manual_market_observation"},
                "observed_at": "2026-09-04T08:00:00+00:00",
            }
        ]
    )
    assert evidence == {}
