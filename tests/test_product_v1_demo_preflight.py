from __future__ import annotations

from pathlib import Path

from scripts.run_product_v1_demo_preflight import build_demo_preflight


def _payload() -> dict[str, object]:
    job = {
        "silver_job_id": 42,
        "product_rank": 1,
        "title": "Machine Learning Engineer",
        "company_name": "Example GmbH",
        "canonical_source_type": "employer_origin",
        "origin_validation_status": "validated",
        "activity_status": "active",
        "hard_filter_status": "passed",
        "product_readiness_status": "rankable",
        "overall_quality_score": 86.5,
    }
    return {
        "summary": {
            "current_active_job_count": 3,
            "rankable_job_count": 2,
            "top_job_count": 1,
        },
        "top_jobs": [job],
        "application_readiness": [
            {
                "silver_job_id": 42,
                "application_readiness_status": "ready_for_generation",
            }
        ],
        "application_sources_ready": {
            "base_cv": True,
            "base_application_letter": True,
        },
        "source_connector_overview": {
            "sources": [
                {
                    "source_name": "example",
                    "connector": {"implemented": True},
                    "activation": {"active": True},
                    "last_ingestion": {"status": "success"},
                    "layers": {"bronze_count": 5, "silver_count": 4},
                }
            ]
        },
    }


def _facts() -> dict[str, object]:
    return {
        "profile_present": True,
        "profile_status": "approved",
        "profile_sha256": "a" * 64,
        "approved_fact_count": 8,
    }


def test_pass_requires_real_top_job_sources_facts_docs_frontend_and_provider_key(
    tmp_path: Path,
) -> None:
    (tmp_path / "index.html").write_text("demo", encoding="utf-8")

    report = build_demo_preflight(
        payload=_payload(),
        candidate_fact_readiness=_facts(),
        frontend_dist=tmp_path,
        openai_key_present=True,
    )

    assert report["state"] == "pass"
    assert report["blocking_gates"] == []
    assert report["selected_top_job"]["silver_job_id"] == 42
    assert len(report["demo_sources"]) == 1
    assert report["boundaries"]["database_writes"] is False
    assert report["boundaries"]["provider_requests"] == 0
    assert report["boundaries"]["submission_writes"] == 0


def test_aggregator_top_job_is_not_promoted_into_application_demo(tmp_path: Path) -> None:
    payload = _payload()
    payload["top_jobs"][0]["canonical_source_type"] = "aggregator"
    (tmp_path / "index.html").write_text("demo", encoding="utf-8")

    report = build_demo_preflight(
        payload=payload,
        candidate_fact_readiness=_facts(),
        frontend_dist=tmp_path,
        openai_key_present=True,
    )

    assert report["state"] == "blocked"
    assert report["selected_top_job"] is None
    assert "authoritative_top_job" in report["blocking_gates"]
    assert "application_readiness" in report["blocking_gates"]


def test_missing_candidate_facts_and_base_letter_fail_closed(tmp_path: Path) -> None:
    payload = _payload()
    payload["application_sources_ready"]["base_application_letter"] = False
    facts = _facts()
    facts["profile_status"] = "draft"
    facts["approved_fact_count"] = 0
    (tmp_path / "index.html").write_text("demo", encoding="utf-8")

    report = build_demo_preflight(
        payload=payload,
        candidate_fact_readiness=facts,
        frontend_dist=tmp_path,
        openai_key_present=False,
    )

    assert report["state"] == "blocked"
    assert "candidate_fact_profile" in report["blocking_gates"]
    assert "base_application_letter" in report["blocking_gates"]
    assert "draft_provider_key" in report["blocking_gates"]
