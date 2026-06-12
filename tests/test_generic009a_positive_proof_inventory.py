from __future__ import annotations

from src.search_intelligence.generic009a_positive_proof_inventory import build_positive_proof_inventory


def test_positive_proof_inventory_finds_strong_and_origin_coverage() -> None:
    rows = [
        {
            "company_key": "e_on_grid_solutions",
            "company_name": "E.ON Grid Solutions GmbH",
            "candidate_url": "https://jobs.eon.com/en",
            "source_type_candidate": "employer_origin_career_site",
            "source_name_candidate": "e_on_grid_solutions:discovery",
            "status": "discovery",
            "notes": "source_decision=create_candidate_recommended; reviewed_by=jens",
        }
    ]

    report = build_positive_proof_inventory(rows, generated_at="2026-06-13T00:00:00+00:00")

    assert report["overall_status"] == "ready_for_positive_control_review"
    assert "e_on_grid_solutions" in report["summary"]["recommended_positive_control_keys"]
    assert "strong_candidate_count" in report["summary"]["covered_gap_ids"]
    assert "clear_career_origin_coverage" in report["summary"]["covered_gap_ids"]
    assert report["safety_boundary"]["candidate_creation"] is False
    assert report["safety_boundary"]["gate_decision"] is False


def test_positive_proof_inventory_tracks_provider_backed_coverage() -> None:
    rows = [
        {
            "company_key": "provider_case",
            "company_name": "Provider Case GmbH",
            "candidate_url": "https://boards.greenhouse.io/providercase",
            "source_type_candidate": "ats_provider_career_site",
            "source_name_candidate": "provider_case:greenhouse",
            "status": "manual_review_required",
            "notes": "source_decision=manual_review_required",
        }
    ]

    report = build_positive_proof_inventory(rows)

    assert "provider_backed_origin_coverage" in report["summary"]["covered_gap_ids"]
    assert "provider_case" in report["gap_to_candidate_keys"]["positive_control_coverage"]


def test_positive_proof_inventory_does_not_create_candidates() -> None:
    report = build_positive_proof_inventory([])

    assert report["overall_status"] == "needs_positive_control_candidates"
    assert report["summary"]["recommended_positive_control_count"] == 0
    assert report["safety_boundary"]["database_writes"] is False
    assert report["safety_boundary"]["connector_activation"] is False
