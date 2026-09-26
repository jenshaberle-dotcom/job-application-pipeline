from scripts.run_freeze2_pre_candidate_origin_resolution import (
    build_summary,
    resolution_state,
    select_review_items,
)


def test_selects_only_new_review_candidates_from_s06_payload() -> None:
    payload = {
        "review": {
            "items": [
                {
                    "company_key": "assemblyai",
                    "company_name": "AssemblyAI",
                    "decision": "manual_review_required",
                    "evidence_count": 1,
                    "source_name": "linkedin",
                },
                {
                    "company_key": "hdi",
                    "company_name": "HDI Group",
                    "decision": "already_known",
                    "evidence_count": 4,
                    "source_name": "linkedin",
                },
                {
                    "company_key": "audi",
                    "company_name": "AUDI AG",
                    "decision": "create_candidate_recommended",
                    "evidence_count": 2,
                    "source_name": "linkedin",
                },
            ]
        }
    }

    items = select_review_items(payload)

    assert [item["company_key"] for item in items] == ["assemblyai", "audi"]
    assert items[0]["sensor_decision"] == "manual_review_required"
    assert items[1]["sensor_decision"] == "create_candidate_recommended"


def test_origin_resolution_requires_selected_url_for_resolved_state() -> None:
    assert (
        resolution_state(
            "origin_url_candidate_selected",
            "https://careers.example.com/",
        )
        == "direct_source_resolved"
    )
    assert (
        resolution_state("origin_url_candidate_selected", None)
        == "direct_source_unresolved"
    )
    assert (
        resolution_state("manual_review_required", None)
        == "direct_source_review_required"
    )
    assert resolution_state("not_found", None) == "direct_source_unresolved"


def test_summary_keeps_all_effect_counts_zero() -> None:
    summary = build_summary(
        [
            {
                "resolution_state": "direct_source_resolved",
                "direct_http_request_count": 3,
            },
            {
                "resolution_state": "direct_source_review_required",
                "direct_http_request_count": 2,
            },
            {
                "resolution_state": "direct_source_unresolved",
                "direct_http_request_count": 1,
            },
        ]
    )

    assert summary["company_count"] == 3
    assert summary["direct_source_resolved"] == 1
    assert summary["direct_source_review_required"] == 1
    assert summary["direct_source_unresolved"] == 1
    assert summary["total_direct_http_requests"] == 6
    assert summary["provider_search_requests"] == 0
    assert summary["database_writes"] == 0
    assert summary["candidate_creations"] == 0
    assert summary["source_activations"] == 0
