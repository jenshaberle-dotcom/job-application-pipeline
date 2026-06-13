from src.search_intelligence.provider001a_provider_backed_origin_preflight import build_provider_backed_origin_preflight


def test_provider_preflight_reports_missing_when_no_provider_hint_exists() -> None:
    report = build_provider_backed_origin_preflight(
        [
            {
                "company_key": "deloitte",
                "company_name": "Deloitte",
                "candidate_url": "https://careers.deloitte.com/",
                "source_name_candidate": "deloitte:discovery",
                "source_type_candidate": "employer_origin_career_site",
            }
        ],
        generated_at="2026-06-13T01:40:00+00:00",
    )

    assert report["overall_status"] == "provider_backed_origin_coverage_missing"
    assert report["summary"]["missing_gap_ids"] == ["provider_backed_origin_coverage"]


def test_provider_preflight_detects_provider_backed_origin_hint() -> None:
    report = build_provider_backed_origin_preflight(
        [
            {
                "company_key": "sample_personio",
                "company_name": "Sample Personio GmbH",
                "candidate_url": "https://sample.jobs.personio.de/",
                "source_name_candidate": "sample:personio",
                "source_type_candidate": "employer_origin_career_site",
            }
        ]
    )

    assert report["overall_status"] == "provider_backed_origin_candidates_found"
    assert report["summary"]["provider_backed_candidate_keys"] == ["sample_personio"]
    assert report["summary"]["missing_gap_ids"] == []
