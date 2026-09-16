from scripts.run_f4b_operator_gate_packet import (
    build_packet,
    classify_geography_candidate,
    review_binding_status,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "silver_job_id": 101,
        "company_name": "Example GmbH",
        "title": "Data Engineer",
        "source_name": "generic_origin:example",
        "source_url": "https://example.com/jobs/101",
        "origin_validation_status": "validated",
        "product_readiness_status": "hard_filter_evidence_required",
        "country": "Germany",
        "city": "Hannover",
        "work_model": "hybrid",
        "commute_minutes": 35,
        "assessment_updated_at": "2026-09-15T12:00:00+00:00",
        "ranking_factors": {"detail_description_sha256": "a" * 64},
        "hard_filter_status": "manual_review_required",
        "hard_filter_reasons": {
            "employment": "manual_review_required",
            "languages": "passed",
            "weekly_hours": "passed",
            "seniority_and_capability_fit": "manual_review_required",
        },
        "sidecar_evidence_hash": "b" * 64,
        "sidecar_payload": {
            "fields": {
                "job_skills": {
                    "status": "observed_bounded_text",
                    "values": ["Python", "SQL"],
                }
            }
        },
        "review_id": 9,
        "review_decision": "passed",
        "review_profile_sha256": "c" * 64,
        "review_detail_sha256": "a" * 64,
        "review_assessment_updated_at": "2026-09-15T12:00:00+00:00",
        "review_fact_keys": ["fact.one"],
    }
    row.update(overrides)
    return row


def test_approved_geography_projection_preserves_remote_and_commute_semantics() -> None:
    assert classify_geography_candidate(
        country="Germany", work_model="remote", commute_minutes=None
    ) == ("passed", "germany_remote_admissible_pd020_pd023")
    assert classify_geography_candidate(
        country="DE", work_model="hybrid", commute_minutes=45
    )[0] == "passed"
    assert classify_geography_candidate(
        country="Germany", work_model="onsite", commute_minutes=46
    )[0] == "failed"
    assert classify_geography_candidate(
        country="Germany", work_model="hybrid", commute_minutes=None
    )[0] == "unknown"
    assert classify_geography_candidate(
        country="Australia", work_model="remote", commute_minutes=None
    )[0] == "failed"


def test_capability_review_binding_is_exact_or_stale_without_rebinding() -> None:
    row = _row()
    status, reasons = review_binding_status(
        row,
        current_profile_sha256="c" * 64,
        valid_fact_keys={"fact.one"},
    )
    assert status == "exact_current"
    assert reasons == ()

    stale = dict(row)
    stale["assessment_updated_at"] = "2026-09-15T13:00:00+00:00"
    status, reasons = review_binding_status(
        stale,
        current_profile_sha256="c" * 64,
        valid_fact_keys={"fact.one"},
    )
    assert status == "stale"
    assert "assessment_revision_changed" in reasons


def test_packet_exposes_only_sanitized_overlap_and_records_threshold_conflict() -> None:
    packet = build_packet(
        rows=[_row()],
        candidate_capability_tags={"python", "java"},
        valid_fact_keys={"fact.one"},
        profile_version="candidate-v1",
        profile_sha256="c" * 64,
        runtime_minimum_quality_score=60,
        policy_version="product-v1-2026-09-03",
        source_sha="deadbeef",
    )

    item = packet["rows"][0]
    assert item["observed_job_skill_count"] == 2
    assert item["exact_candidate_skill_match_count"] == 1
    assert item["exact_candidate_skill_unmatched_count"] == 1
    assert item["exact_candidate_skill_coverage"] == 0.5
    assert item["capability_overlap_class"] == "partial_exact_coverage"
    assert item["capability_review_binding"] == "exact_current"

    threshold = packet["ranking_threshold"]
    assert threshold["runtime_minimum_quality_score"] == 60.0
    assert threshold["canonical_pd051_minimum_quality_score"] == 70.0
    assert threshold["matches_canonical_pd051"] is False

    serialized = str(packet)
    assert "fact.one" not in serialized
    assert "python" not in serialized.casefold()
    assert "java" not in serialized.casefold()
    assert "candidate_fact_keys" not in serialized
    assert "review_rationale" not in serialized
    assert packet["boundaries"]["database_writes"] is False
    assert packet["boundaries"]["ranking_authority_changed"] is False


def test_packet_does_not_turn_missing_job_skill_evidence_into_negative_fit() -> None:
    row = _row(sidecar_payload=None, review_id=None, review_fact_keys=None)
    packet = build_packet(
        rows=[row],
        candidate_capability_tags={"python"},
        valid_fact_keys={"fact.one"},
        profile_version="candidate-v1",
        profile_sha256="c" * 64,
        runtime_minimum_quality_score=70,
        policy_version="product-v1-2026-08-02",
        source_sha="deadbeef",
    )
    item = packet["rows"][0]
    assert item["capability_overlap_class"] == "not_observed"
    assert item["exact_candidate_skill_coverage"] is None
    assert item["capability_review_binding"] == "missing"
    assert packet["ranking_threshold"]["matches_canonical_pd051"] is True
