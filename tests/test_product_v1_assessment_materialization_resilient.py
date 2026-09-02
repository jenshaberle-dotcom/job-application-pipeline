from __future__ import annotations

from scripts import run_product_v1_assessment_materialization_resilient as resilient
from src.search_intelligence.product_v1_downstream_preview import DownstreamPreviewStop


SOURCE = "personio:example"
DETAIL = """
Permanent employment. Fluent German and English are required.
This is a hybrid work model with 35-40 hours per week.
We are looking for a Senior Engineer for a senior-level role.
"""


def _row(
    silver_job_id: int,
    *,
    persisted_description: str | None = None,
) -> dict[str, object]:
    url = f"https://example.jobs.personio.de/job/{silver_job_id}?language=de"
    job = {"source_url": url, "title": "Senior Data Engineer"}
    if persisted_description is not None:
        job["description"] = persisted_description
    return {
        "silver_job_id": silver_job_id,
        "raw_job_id": silver_job_id + 1000,
        "source_name": SOURCE,
        "source_url": url,
        "title": "Senior Data Engineer",
        "origin_validation_status": None,
        "product_readiness_status": "assessment_required",
        "lifecycle_status": "active_confirmed",
        "lifecycle_evidence_reason": "authoritative_verified_ats_feed_observation",
        "latest_health_coverage": "complete_inventory",
        "latest_observation_observed_at": "2026-09-02T12:00:00+00:00",
        "latest_observation_source_url": url,
        "latest_observation_evidence": {
            "source_url": url,
            "raw_evidence": {
                "source_type": "employer_origin_ats_backed_career_site",
                "job": job,
                "ats_feed_authority": {"product_authority": False},
            },
        },
    }


def test_http_429_blocks_only_one_candidate_and_plan_completes(monkeypatch) -> None:
    calls: list[str] = []

    def fetch(url: str) -> tuple[str, str, str]:
        calls.append(url)
        if url.endswith("/1?language=de"):
            raise DownstreamPreviewStop("preview detail returned HTTP 429")
        return url, "Senior Data Engineer", DETAIL

    monkeypatch.setattr(resilient, "_CANONICAL_FETCH", fetch)

    plan = resilient.build_plan_isolated(
        rows=[_row(1), _row(2)],
        authorized_sources={SOURCE},
        policy_version="product-v1-2026-08-02",
    )

    assert plan["candidate_count"] == 2
    assert plan["proposal_count"] == 1
    assert plan["blocked_count"] == 1
    assert plan["proposals"][0]["silver_job_id"] == 2
    assert plan["blocked"] == [
        {
            "silver_job_id": 1,
            "source_name": SOURCE,
            "title": "Senior Data Engineer",
            "reason": "preview detail returned HTTP 429",
        }
    ]
    assert plan["boundaries"]["network_exact_detail_targets"] == 2
    assert plan["boundaries"]["current_observation_detail_reuse"] == 0
    assert plan["boundaries"]["network_retry_requests"] == 0
    assert calls == [
        "https://example.jobs.personio.de/job/1?language=de",
        "https://example.jobs.personio.de/job/2?language=de",
    ]


def test_current_exact_observation_description_avoids_network(monkeypatch) -> None:
    calls: list[str] = []

    def fetch(url: str) -> tuple[str, str, str]:
        calls.append(url)
        raise AssertionError("network fallback must not run")

    monkeypatch.setattr(resilient, "_CANONICAL_FETCH", fetch)

    plan = resilient.build_plan_isolated(
        rows=[_row(3, persisted_description=DETAIL)],
        authorized_sources={SOURCE},
        policy_version="product-v1-2026-08-02",
    )

    assert plan["proposal_count"] == 1
    assert plan["blocked_count"] == 0
    assert plan["boundaries"]["network_exact_detail_targets"] == 0
    assert plan["boundaries"]["current_observation_detail_reuse"] == 1
    assert plan["boundaries"]["network_retry_requests"] == 0
    assert calls == []
    assessment = plan["proposals"][0]["assessment"]
    assert assessment["employment_type"] == "permanent"
    assert assessment["required_languages"] == ["de", "en"]
    assert assessment["work_model"] == "hybrid"


def test_structured_current_observation_extends_normalized_description() -> None:
    row = _row(4, persisted_description="Permanent employment.")
    raw_evidence = row["latest_observation_evidence"]["raw_evidence"]
    raw_evidence["source_specific"] = {
        "raw_position": {
            "jobDescriptions": {
                "jobDescription": [
                    {"name": "Aufgaben", "value": "Build data pipelines."},
                    {
                        "name": "Profil",
                        "value": "Fluent German and English. Hybrid work model.",
                    },
                ]
            }
        }
    }

    detail = resilient._bound_observation_detail(row)

    assert detail is not None
    title, text = detail
    assert title == "Senior Data Engineer"
    assert "Permanent employment." in text
    assert "Build data pipelines." in text
    assert "Fluent German and English. Hybrid work model." in text


def test_mismatched_persisted_observation_description_is_not_reused() -> None:
    row = _row(5, persisted_description=DETAIL)
    row["latest_observation_source_url"] = (
        "https://example.jobs.personio.de/job/other?language=de"
    )

    assert resilient._bound_observation_detail(row) is None


def test_isolation_does_not_retry_or_change_canonical_fetch_result(monkeypatch) -> None:
    calls: list[str] = []
    expected = (
        "https://example.jobs.personio.de/job/6?language=de",
        "Senior Data Engineer",
        DETAIL,
    )

    def fetch(url: str) -> tuple[str, str, str]:
        calls.append(url)
        return expected

    monkeypatch.setattr(resilient, "_CANONICAL_FETCH", fetch)

    assert resilient.fetch_detail_isolated(expected[0]) == expected
    assert calls == [expected[0]]
