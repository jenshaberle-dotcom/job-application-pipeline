from scripts.run_employer_origin_detail_evidence_repair_agent import (
    SourceCandidate,
    concrete_job_detail_url,
    discover_link_candidates,
)
from src.search_intelligence.multi_origin_evidence import (
    DETAIL_URL_SHAPE_VERSION,
    job_detail_url_shape,
)


def test_explicit_jobid_query_detail_is_concrete() -> None:
    url = (
        "https://jobs.example.com/stellenangebote/details/"
        "?jobid=8e116f5e-9555-11f1-8dff-623599f7c92f"
    )

    assert job_detail_url_shape(url)
    assert concrete_job_detail_url(url)


def test_opaque_generic_id_is_concrete_but_weak_ids_fail_closed() -> None:
    assert concrete_job_detail_url("https://karriere.example.com/de?id=51980f")
    assert not concrete_job_detail_url("https://karriere.example.com/de?id=123456")
    assert not concrete_job_detail_url("https://karriere.example.com/de?id=a1b2")


def test_root_level_requisition_filename_is_concrete() -> None:
    url = (
        "https://jobs.example.com/"
        "C-Software-Engineer-for-Cloud-Applications-mwd-de-j3471.html"
    )

    assert job_detail_url_shape(url)
    assert concrete_job_detail_url(url)


def test_obvious_legal_path_stays_rejected_even_with_jobid() -> None:
    url = "https://jobs.example.com/privacy?jobid=abc123"

    assert not job_detail_url_shape(url)
    assert not concrete_job_detail_url(url)


def test_discovery_accepts_query_detail_and_exposes_shape_version() -> None:
    candidate = SourceCandidate(
        id=0,
        company_key="example",
        company_name="Example GmbH",
        candidate_url="https://jobs.example.com/stellenangebote/",
        source_name_candidate="example:discovery",
        source_family_candidate="example",
        source_target_candidate=None,
        source_type_candidate="employer_origin_career_site",
        status="transient_read_only",
        risk_level="low",
    )
    detail_url = "https://jobs.example.com/stellenangebote/details/?jobid=abc123"

    def fetcher(url: str) -> tuple[str, str, int]:
        if url == candidate.candidate_url:
            return (
                f'<html><body><a href="{detail_url}">Example AI Engineer Hannover</a></body></html>',
                url,
                200,
            )
        raise AssertionError(f"Unexpected URL: {url}")

    links, rejected, requested, evidence = discover_link_candidates(
        candidate=candidate,
        gates={},
        profile_terms=("ai",),
        location_terms=("hannover",),
        max_seed_pages=1,
        enable_search_discovery=False,
        fetcher=fetcher,
    )

    assert [link.url for link in links] == [detail_url]
    assert detail_url not in "\n".join(rejected)
    assert requested == (candidate.candidate_url,)
    assert evidence["detail_url_shape_version"] == DETAIL_URL_SHAPE_VERSION
    assert DETAIL_URL_SHAPE_VERSION == "DETAIL-006"
