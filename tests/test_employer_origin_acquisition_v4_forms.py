from __future__ import annotations

from src.connectors.employer_origin_acquisition_v4_forms import (
    MeteredRequest,
    acquire_genuine_job_pages,
)


EMPLOYER = "https://www.example.invalid/careers"
EMPLOYER_HOST = "www.example.invalid"
LISTING = "https://karriere.example.invalid"
LISTING_HOST = "karriere.example.invalid"
DETAIL = "https://karriere.example.invalid/jobs/platform-engineer-12345"


def _job_html() -> str:
    return (
        "<html><title>Platform Engineer</title><body>"
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"JobPosting","title":"Platform Engineer"}'
        "</script>Apply now. Responsibilities and requirements."
        "</body></html>"
    )


def test_strict_post_search_can_use_shared_fourth_request_for_real_detail() -> None:
    calls: list[MeteredRequest] = []

    def fetcher(url: str):
        raise AssertionError(f"plain fetcher should not be used when executor is supplied: {url}")

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(EMPLOYER):
            return f"<html><a href='{LISTING}'>View jobs</a></html>", EMPLOYER, 200
        if request == MeteredRequest(LISTING):
            return (
                "<html><title>Jobs</title><body>"
                "<form method='post' action='/'>"
                "<input name='filter[text]' type='text' value=''>"
                "<input name='filter[zip]' type='text' value=''>"
                "</form></body></html>",
                f"{LISTING}/",
                200,
            )
        if request == MeteredRequest(
            LISTING,
            "POST",
            (("filter[text]", ""), ("filter[zip]", "")),
        ):
            return f"<html><a href='{DETAIL}'>Platform Engineer</a></html>", f"{LISTING}/", 200
        if request == MeteredRequest(DETAIL):
            return _job_html(), DETAIL, 200
        raise AssertionError(request)

    jobs, observed_root = acquire_genuine_job_pages(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=fetcher,
        request_executor=executor,
        max_followup_requests=2,
    )

    assert observed_root == EMPLOYER
    assert calls == [
        MeteredRequest(EMPLOYER),
        MeteredRequest(LISTING),
        MeteredRequest(LISTING, "POST", (("filter[text]", ""), ("filter[zip]", ""))),
        MeteredRequest(DETAIL),
    ]
    assert len(jobs) == 1
    assert jobs[0].final_url == DETAIL
    assert jobs[0].proof_kind == "jsonld_jobposting"


def test_ambiguous_search_forms_do_not_execute_by_ranking_guess() -> None:
    calls: list[MeteredRequest] = []

    def executor(request: MeteredRequest):
        calls.append(request)
        if request == MeteredRequest(EMPLOYER):
            return f"<html><a href='{LISTING}'>View jobs</a></html>", EMPLOYER, 200
        if request == MeteredRequest(LISTING):
            return (
                "<html><body>"
                "<form method='post' action='/jobs'><input name='filter[text]' type='text'></form>"
                "<form method='post' action='/positions'><input name='search' type='text'></form>"
                "</body></html>",
                LISTING,
                200,
            )
        raise AssertionError(request)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST,),
        known_detail_urls=(),
        fetcher=lambda url: (_ for _ in ()).throw(AssertionError(url)),
        request_executor=executor,
        max_followup_requests=2,
    )

    assert calls == [MeteredRequest(EMPLOYER), MeteredRequest(LISTING)]
    assert jobs == []


def test_old_plain_get_fetcher_contract_remains_compatible() -> None:
    calls: list[str] = []

    def fetcher(url: str):
        calls.append(url)
        if url == EMPLOYER:
            return f"<html><a href='{DETAIL}'>Platform Engineer</a></html>", EMPLOYER, 200
        if url == DETAIL:
            return _job_html(), DETAIL, 200
        raise AssertionError(url)

    jobs, _ = acquire_genuine_job_pages(
        listing_url=EMPLOYER,
        allowed_hosts=(EMPLOYER_HOST, LISTING_HOST),
        known_detail_urls=(DETAIL,),
        fetcher=fetcher,
        max_followup_requests=2,
    )

    assert calls == [EMPLOYER, DETAIL]
    assert len(jobs) == 1
