from scripts.product_v1_job_presentation_runtime import enrich_product_payload_for_operator


def _job(job_id: int, *, source_name: str, url: str) -> dict:
    return {
        "silver_job_id": job_id,
        "source_name": source_name,
        "canonical_source_type": "employer_origin_career_site",
        "company_name": "Finanz Informatik GmbH & Co. KG",
        "title": "Data Platform Engineer (m/w/d)",
        "city": "Hannover",
        "source_url": url,
        "work_model": "unknown",
        "lifecycle_status": "active_confirmed",
        "product_readiness_status": "assessment_required",
    }


def _evidence(
    *,
    identifier: str | None = None,
    evidence_kind: str | None = None,
    canonical_url: str | None = None,
) -> dict:
    metadata = {}
    if identifier:
        metadata["structured_identifier"] = identifier
    if evidence_kind:
        metadata["identifier_evidence_kind"] = evidence_kind
    if canonical_url:
        metadata["canonical_origin_url"] = canonical_url
    return {
        "normalized_evidence": {
            "raw_evidence": {"job": {"metadata": metadata}}
        }
    }


def test_cr_f0_001_explicit_identifier_collapses_locale_url_aliases_across_sources() -> None:
    plain = "https://www.f-i.de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d"
    localized = "https://www.f-i.de/de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d"
    payload = {
        "job_readiness": [
            _job(701, source_name="finanz_informatik:hannover", url=plain),
            _job(702, source_name="generic_origin:finanz_informatik", url=localized),
        ],
        "top_jobs": [],
        "summary": {},
        "boundaries": {},
    }
    evidence = {
        701: _evidence(identifier="392/B", evidence_kind="explicit_label"),
        702: _evidence(identifier="392/b", evidence_kind="explicit_label"),
    }

    result = enrich_product_payload_for_operator(payload, observation_evidence=evidence)

    assert [row["silver_job_id"] for row in result["job_readiness"]] == [701]
    assert [row["silver_job_id"] for row in result["duplicate_origin_jobs"]] == [702]


def test_page_declared_canonical_url_can_bridge_one_alias_without_shared_identifier() -> None:
    plain = "https://www.example.de/karriere/jobs/data-engineer"
    localized = "https://www.example.de/de/karriere/jobs/data-engineer"
    payload = {
        "job_readiness": [
            _job(711, source_name="legacy_origin:example", url=plain),
            _job(712, source_name="generic_origin:example", url=localized),
        ],
        "top_jobs": [],
        "summary": {},
        "boundaries": {},
    }
    evidence = {
        712: _evidence(canonical_url=plain),
    }

    result = enrich_product_payload_for_operator(payload, observation_evidence=evidence)

    assert [row["silver_job_id"] for row in result["job_readiness"]] == [711]
    assert [row["silver_job_id"] for row in result["duplicate_origin_jobs"]] == [712]


def test_same_explicit_identifier_on_different_origin_hosts_does_not_collapse() -> None:
    payload = {
        "job_readiness": [
            _job(721, source_name="generic_origin:a", url="https://jobs.example-a.de/job/42"),
            _job(722, source_name="generic_origin:b", url="https://jobs.example-b.de/job/42"),
        ],
        "top_jobs": [],
        "summary": {},
        "boundaries": {},
    }
    evidence = {
        721: _evidence(identifier="REQ-42", evidence_kind="explicit_label"),
        722: _evidence(identifier="REQ-42", evidence_kind="explicit_label"),
    }

    result = enrich_product_payload_for_operator(payload, observation_evidence=evidence)

    assert [row["silver_job_id"] for row in result["job_readiness"]] == [721, 722]
    assert result["duplicate_origin_jobs"] == []


def test_unqualified_legacy_identifier_remains_source_local() -> None:
    url_a = "https://jobs.example.de/location-a/req-42"
    url_b = "https://jobs.example.de/location-b/req-42"
    payload = {
        "job_readiness": [
            _job(731, source_name="origin:a", url=url_a),
            _job(732, source_name="origin:b", url=url_b),
        ],
        "top_jobs": [],
        "summary": {},
        "boundaries": {},
    }
    evidence = {
        731: _evidence(identifier="REQ-42"),
        732: _evidence(identifier="REQ-42"),
    }

    result = enrich_product_payload_for_operator(payload, observation_evidence=evidence)

    assert [row["silver_job_id"] for row in result["job_readiness"]] == [731, 732]
    assert result["duplicate_origin_jobs"] == []
