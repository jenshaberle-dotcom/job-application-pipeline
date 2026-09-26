from __future__ import annotations

from scripts import run_freeze2_sensor_candidate_expansion_review as bridge
from src.search_intelligence.candidate_expansion import KnownCandidate


def _sensor_report() -> dict[str, object]:
    return {
        "schema": "job_application_pipeline.freeze2_market_sensor_probe.v1",
        "provider": "tavily",
        "sensors": {
            "linkedin": {
                "queries": [
                    {
                        "search_term": "AI Architect",
                        "location_signal": "Hannover",
                        "query": 'site:linkedin.com/jobs/view "AI Architect" "Hannover" Germany',
                    }
                ],
                "observations": [
                    {
                        "query": 'site:linkedin.com/jobs/view "AI Architect" "Hannover" Germany',
                        "title_signal": "Business Analyst / AI Engineer bei HDI Group — Hannover",
                        "snippet_signal": "Bewerben Sie sich für die Stelle bei HDI Group in Hannover.",
                        "observed_at_utc": "2026-09-26T10:31:57+00:00",
                    },
                    {
                        "query": 'site:linkedin.com/jobs/view "AI Architect" "Hannover" Germany',
                        "title_signal": "Senior AI Engineer (m/f/d)",
                        "snippet_signal": "Get notified about new AI jobs in Hannover.",
                        "observed_at_utc": "2026-09-26T10:31:57+00:00",
                    },
                ],
            },
            "indeed": {
                "queries": [
                    {
                        "search_term": "Agentic AI",
                        "location_signal": "30629",
                        "query": 'site:de.indeed.com/viewjob "Agentic AI" "30629" Germany',
                    }
                ],
                "observations": [
                    {
                        "query": 'site:de.indeed.com/viewjob "Agentic AI" "30629" Germany',
                        "title_signal": "AI Solution Architect (m/w/d) - 30938 Burgwedel",
                        "snippet_signal": (
                            "AI Solution Architect (m/w/d) Dirk Rossmann GmbH · "
                            "2.8 30938 Burgwedel"
                        ),
                        "observed_at_utc": "2026-09-26T10:31:57+00:00",
                    }
                ],
            },
        },
    }


def test_groups_only_explicit_company_evidence_from_legacy_sensor_artifact() -> None:
    observations, metadata = bridge._build_company_observations(_sensor_report())

    assert metadata["total_sensor_observation_count"] == 3
    assert metadata["attributed_observation_count"] == 2
    assert metadata["unattributed_observation_count"] == 1
    assert metadata["attributed_company_count"] == 2

    by_key = {item.company_key: item for item in observations}
    assert by_key["hdi"].company_name == "HDI Group"
    assert by_key["hdi"].search_terms == ("AI Architect",)
    assert by_key["dirk_rossmann"].company_name == "Dirk Rossmann GmbH"
    assert by_key["dirk_rossmann"].search_terms == ("Agentic AI",)


def test_review_reuses_known_candidate_suppression_without_creating_candidates(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        bridge,
        "_load_known_candidates",
        lambda: [
            KnownCandidate(
                candidate_id=42,
                company_key="hdi",
                company_name="HDI Group",
                status="active_controlled",
                source_family_candidate="generic_origin",
            )
        ],
    )

    report = bridge.build_report(_sensor_report())
    items = {item["company_key"]: item for item in report["review"]["items"]}

    assert report["baseline_candidate_count"] == 1
    assert items["hdi"]["decision"] == "active_candidate_monitoring"
    assert items["dirk_rossmann"]["decision"] == "manual_review_required"
    assert report["summary"]["review_create_recommended_count"] == 0
    assert report["summary"]["review_manual_review_count"] == 1
    assert report["summary"]["review_already_known_count"] == 1
    assert report["boundary"]["external_provider_requests"] == 0
    assert report["boundary"]["database_writes"] == 0
    assert report["boundary"]["candidate_creation"] == 0
