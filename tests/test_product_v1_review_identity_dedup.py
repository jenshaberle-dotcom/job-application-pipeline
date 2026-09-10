from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator


def _job(job_id: int, *, url: str, title: str = "AI Engineer / KI-Entwickler (m/w/d)") -> dict:
    return {
        "silver_job_id": job_id,
        "source_name": "finanz_informatik:hannover",
        "canonical_source_type": "employer_origin_career_site",
        "company_name": "Finanz Informatik GmbH & Co. KG",
        "title": title,
        "city": "Hannover",
        "source_url": url,
        "work_model": "unknown",
        "lifecycle_status": "active_confirmed",
        "product_readiness_status": "assessment_required",
    }


def test_exact_same_origin_url_collapses_duplicate_review_rows() -> None:
    canonical = "https://www.f-i.de/de/karriere/offene-stellen/ai-engineer-m-w-d"
    payload = {
        "job_readiness": [_job(600, url=canonical), _job(601, url=canonical + "/")],
        "top_jobs": [],
        "summary": {},
        "boundaries": {},
    }

    result = enrich_product_payload_for_operator(payload, observation_evidence={})

    assert [item["silver_job_id"] for item in result["job_readiness"]] == [600]
    assert [item["silver_job_id"] for item in result["duplicate_origin_jobs"]] == [601]
    assert result["summary"]["exact_origin_duplicate_review_excluded_job_count"] == 1


def test_exact_same_origin_url_collapses_across_employer_origin_source_projections() -> None:
    canonical = "https://www.f-i.de/de/karriere/offene-stellen/business-analyst-obb-pro"
    legacy = _job(605, url=canonical)
    generic = _job(606, url=canonical + "/")
    generic["source_name"] = "generic_origin:finanz_informatik"
    generic["canonical_source_type"] = "employer_origin_ats_backed_career_site"
    payload = {
        "job_readiness": [legacy, generic],
        "top_jobs": [],
        "summary": {},
        "boundaries": {},
    }

    result = enrich_product_payload_for_operator(payload, observation_evidence={})

    assert [item["silver_job_id"] for item in result["job_readiness"]] == [605]
    assert [item["silver_job_id"] for item in result["duplicate_origin_jobs"]] == [606]
    assert result["boundaries"]["review_dedup_exact_origin_url_may_cross_source_projections"] is True


def test_same_title_company_with_different_origin_urls_remains_two_vacancies() -> None:
    payload = {
        "job_readiness": [
            _job(610, url="https://www.f-i.de/de/karriere/offene-stellen/ai-engineer-one"),
            _job(611, url="https://www.f-i.de/de/karriere/offene-stellen/ai-engineer-two"),
        ],
        "top_jobs": [],
        "summary": {},
        "boundaries": {},
    }

    result = enrich_product_payload_for_operator(payload, observation_evidence={})

    assert [item["silver_job_id"] for item in result["job_readiness"]] == [610, 611]
    assert result["duplicate_origin_jobs"] == []
    assert result["boundaries"]["title_company_similarity_alone_never_merges_vacancies"] is True


def test_structured_identifier_collapses_url_variants_within_same_source() -> None:
    payload = {
        "job_readiness": [
            _job(620, url="https://jobs.example.test/location-a/req-42"),
            _job(621, url="https://jobs.example.test/location-b/req-42"),
        ],
        "top_jobs": [],
        "summary": {},
        "boundaries": {},
    }
    observation_evidence = {
        620: {
            "normalized_evidence": {
                "raw_evidence": {"job": {"metadata": {"structured_identifier": "REQ-42"}}}
            }
        },
        621: {
            "normalized_evidence": {
                "raw_evidence": {"job": {"metadata": {"structured_identifier": "REQ-42"}}}
            }
        },
    }

    result = enrich_product_payload_for_operator(
        payload,
        observation_evidence=observation_evidence,
    )

    assert len(result["job_readiness"]) == 1
    assert len(result["duplicate_origin_jobs"]) == 1
