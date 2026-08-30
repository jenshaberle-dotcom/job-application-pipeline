from __future__ import annotations

from scripts.run_deterministic_detail_form_carrier_audit import audit_payload, classify_form


def test_get_jobish_search_form_is_not_detail_identifier_carrier() -> None:
    form = {
        "method": "get",
        "action": {
            "scheme": "https",
            "host": "jobs.example.invalid",
            "path": "/search",
            "query_keys": [],
        },
        "field_names": ["q", "location", "department"],
    }

    result = classify_form(form)

    assert result["classification"] == "get_jobish_search_or_filter_form"
    assert result["semantic_identifier_fields"] == []
    assert result["search_filter_fields"] == ["department", "location", "q"]


def test_post_jobish_semantic_identifier_form_is_visible_but_not_submitted() -> None:
    form = {
        "method": "post",
        "action": {
            "scheme": "https",
            "host": "jobs.example.invalid",
            "path": "/jobs/detail",
            "query_keys": [],
        },
        "field_names": ["candidateObjectId", "csrfToken"],
    }

    result = classify_form(form)

    assert result["classification"] == "post_jobish_with_semantic_identifier_field"
    assert result["semantic_identifier_fields"] == ["candidateObjectId"]
    assert "csrfToken" in result["field_names"]


def test_numeric_action_segments_are_structurally_normalized() -> None:
    form = {
        "method": "get",
        "action": {
            "scheme": "https",
            "host": "jobs.example.invalid",
            "path": "/jobs/12345/detail",
            "query_keys": [],
        },
        "field_names": ["jobObjectId"],
    }

    result = classify_form(form)

    assert result["action"]["path_pattern"] == "/jobs/:num/detail"
    assert result["classification"] == "get_jobish_with_semantic_identifier_field"


def test_payload_selects_only_reclassified_form_cases_and_has_zero_effect_boundary() -> None:
    payload = {
        "schema": "source.v1",
        "results": [
            {
                "company_key": "alpha",
                "company_name": "Alpha",
                "classification": "form_driven_detail_surface",
                "page_summaries": [
                    {
                        "form_detail_signal": True,
                        "provider_hints": [],
                        "forms": [
                            {
                                "method": "get",
                                "action": {
                                    "scheme": "https",
                                    "host": "jobs.alpha.invalid",
                                    "path": "/jobs/search",
                                    "query_keys": [],
                                },
                                "field_names": ["q"],
                            }
                        ],
                    }
                ],
            },
            {
                "company_key": "beta",
                "company_name": "Beta",
                "classification": "unclassified_jobish_detail_surface",
                "page_summaries": [],
            },
        ],
    }

    result = audit_payload(payload)

    assert result["boundary"]["input_form_driven_cases"] == 1
    assert result["boundary"]["network_requests"] == 0
    assert result["boundary"]["form_submissions"] == 0
    assert result["boundary"]["form_values_read"] == 0
    assert result["boundary"]["database_writes"] == 0
    assert result["results"][0]["company_key"] == "alpha"
