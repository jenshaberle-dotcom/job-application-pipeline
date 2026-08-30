from __future__ import annotations

from scripts.run_deterministic_detail_identifier_reclassification import (
    high_confidence_unknown_identifier_key,
    reclassify_case,
    reclassify_page,
    reclassify_payload,
)


def _page(**overrides):
    page = {
        "classification": "unknown_query_identifier_key_surface",
        "trusted_query_detail_count": 0,
        "unknown_identifier_query_keys": {},
        "form_detail_signal": False,
        "unclassified_jobish_anchor_count": 0,
        "client_markers": [],
        "script_job_markers": [],
        "provider_hints": [],
    }
    page.update(overrides)
    return page


def test_weobjectid_is_retained_as_semantic_unknown_identifier() -> None:
    assert high_confidence_unknown_identifier_key("we_objectID") is True
    result = reclassify_page(
        _page(unknown_identifier_query_keys={"weobjectid": 4})
    )
    assert result["classification"] == "unknown_query_identifier_key_surface"
    assert result["unknown_identifier_query_keys"] == {"weobjectid": 4}
    assert result["suppressed_unknown_identifier_query_keys"] == {}


def test_tracking_and_incidental_id_substrings_are_suppressed() -> None:
    for key in ("linkid", "igshid", "icid", "cid", "dualemstudiumbeidercgm"):
        assert high_confidence_unknown_identifier_key(key) is False

    result = reclassify_page(
        _page(
            unknown_identifier_query_keys={"icid": 218},
            unclassified_jobish_anchor_count=12,
        )
    )
    assert result["classification"] == "unclassified_jobish_detail_surface"
    assert result["unknown_identifier_query_keys"] == {}
    assert result["suppressed_unknown_identifier_query_keys"] == {"icid": 218}


def test_plural_filter_ids_do_not_become_detail_identity() -> None:
    assert high_confidence_unknown_identifier_key("besoldungsentgeltgruppeids") is False
    result = reclassify_page(
        _page(
            unknown_identifier_query_keys={"besoldungsentgeltgruppeids": 1},
            provider_hints=["example_provider"],
        )
    )
    assert result["classification"] == "provider_detail_route_gap"


def test_fallback_priority_uses_existing_structural_evidence_only() -> None:
    form = reclassify_page(
        _page(
            unknown_identifier_query_keys={"linkid": 1},
            form_detail_signal=True,
            unclassified_jobish_anchor_count=5,
        )
    )
    assert form["classification"] == "form_driven_detail_surface"

    client = reclassify_page(
        _page(
            unknown_identifier_query_keys={"cid": 1},
            client_markers=["__next_data__"],
        )
    )
    assert client["classification"] == "client_rendered_or_script_detail_surface"


def test_case_and_payload_reclassification_are_offline_and_auditable() -> None:
    source = {
        "schema": "job_application_pipeline.deterministic_detail_surface_audit.v1",
        "results": [
            {
                "company_key": "iph",
                "classification": "unknown_query_identifier_key_surface",
                "current_v4_now_resolves_detail": False,
                "page_summaries": [
                    _page(unknown_identifier_query_keys={"weobjectid": 12})
                ],
            },
            {
                "company_key": "tracking_noise",
                "classification": "unknown_query_identifier_key_surface",
                "current_v4_now_resolves_detail": False,
                "page_summaries": [
                    _page(
                        unknown_identifier_query_keys={"igshid": 3},
                        unclassified_jobish_anchor_count=8,
                    )
                ],
            },
        ],
    }

    output = reclassify_payload(source)

    assert output["summary"]["classification_counts_before"] == {
        "unknown_query_identifier_key_surface": 2
    }
    assert output["summary"]["classification_counts_after"] == {
        "unclassified_jobish_detail_surface": 1,
        "unknown_query_identifier_key_surface": 1,
    }
    assert output["retained_identifier_keys"] == {"iph": {"weobjectid": 12}}
    assert output["suppressed_identifier_keys"] == {
        "tracking_noise": {"igshid": 3}
    }
    assert output["boundary"]["network_requests"] == 0
    assert output["boundary"]["database_reads"] == 0
    assert output["boundary"]["query_values_read"] == 0
    assert output["boundary"]["query_values_persisted"] == 0

    case = reclassify_case(
        {
            "company_key": "drift",
            "classification": "unknown_query_identifier_key_surface",
            "current_v4_now_resolves_detail": True,
            "page_summaries": [_page(unknown_identifier_query_keys={"icid": 1})],
        }
    )
    assert case["classification"] == "current_v4_now_resolves_detail"
