from __future__ import annotations

from scripts import run_product_v1_assessment_materialization_resilient as resilient
from src.search_intelligence.product_v1_downstream_preview import DownstreamPreviewStop


SOURCE = "personio:example"
DETAIL = """
Permanent employment. Fluent German and English are required.
This is a hybrid work model with 35-40 hours per week.
We are looking for a Senior Engineer for a senior-level role.
"""


def _row(silver_job_id: int) -> dict[str, object]:
    url = f"https://example.jobs.personio.de/job/{silver_job_id}?language=de"
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
                "job": {"source_url": url, "title": "Senior Data Engineer"},
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
    assert calls == [
        "https://example.jobs.personio.de/job/1?language=de",
        "https://example.jobs.personio.de/job/2?language=de",
    ]


def test_isolation_does_not_retry_or_change_canonical_fetch_result(monkeypatch) -> None:
    calls: list[str] = []
    expected = (
        "https://example.jobs.personio.de/job/3?language=de",
        "Senior Data Engineer",
        DETAIL,
    )

    def fetch(url: str) -> tuple[str, str, str]:
        calls.append(url)
        return expected

    monkeypatch.setattr(resilient, "_CANONICAL_FETCH", fetch)

    assert resilient.fetch_detail_isolated(expected[0]) == expected
    assert calls == [expected[0]]
