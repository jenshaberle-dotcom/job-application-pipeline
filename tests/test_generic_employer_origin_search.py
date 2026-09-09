from __future__ import annotations

from src.connectors.employer_origin_acquisition import AcquiredJobPage, parse_page
from src.connectors.employer_origin_form_navigation import JobSearchFormRequest
from src.connectors import generic_employer_origin_search as search


def _job(url: str, title: str) -> AcquiredJobPage:
    return AcquiredJobPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        title=title,
        html_bytes=500,
        proof_kind="jsonld_jobposting",
        discovery_source="targeted_search:anchor_detail",
        anchor_text="",
    )


def test_bind_search_form_changes_only_keyword_field() -> None:
    form = JobSearchFormRequest(
        url="https://example.test/jobs",
        method="GET",
        fields=(("keyword", ""), ("location", "Hannover"), ("lang", "de")),
    )

    request = search.bind_search_form(form, "Data Engineer")

    assert request is not None
    assert request.payload_kind == "query"
    assert dict(request.fields) == {
        "keyword": "Data Engineer",
        "location": "Hannover",
        "lang": "de",
    }


def test_form_search_follows_explicit_next_page_and_collects_multiple_jobs(
    monkeypatch,
) -> None:
    root = parse_page(
        requested_url="https://example.test/careers",
        final_url="https://example.test/careers",
        status_code=200,
        html="""
        <html><title>Careers</title><body>
          <form action="/jobs" method="get">
            <input name="keyword" value="">
            <input name="location" value="">
          </form>
        </body></html>
        """,
    )
    calls: list[search.SearchRequest] = []

    def execute(request: search.SearchRequest) -> tuple[str, str, int]:
        calls.append(request)
        if "page=2" in request.url:
            return (
                '<html><a href="/job/2">Data Engineer II</a></html>',
                request.url,
                200,
            )
        assert dict(request.fields)["keyword"] == "Data Engineer"
        return (
            """
            <html><body>
              <a href="/job/1">Data Engineer I</a>
              <a href="/jobs?keyword=Data+Engineer&page=2">Next</a>
            </body></html>
            """,
            "https://example.test/jobs?keyword=Data+Engineer",
            200,
        )

    def prove(**kwargs):
        url = kwargs["detail_url"]
        return _job(url, "Data Engineer")

    monkeypatch.setattr(search, "_prove_html_detail", prove)

    outcome = search.search_form_surface(
        root=root,
        query="Data Engineer",
        allowed_hosts=("example.test",),
        execute=execute,
        page_cap=3,
        job_cap=10,
    )

    assert outcome is not None
    assert outcome.mechanism == "strict_html_form"
    assert outcome.pages_requested == 2
    assert outcome.exhausted is True
    assert outcome.stop_reason == "no_next_page"
    assert len(outcome.jobs) == 2
    assert {job.final_url for job in outcome.jobs} == {
        "https://example.test/job/1",
        "https://example.test/job/2",
    }
    assert len(calls) == 2


def test_search_reports_no_targeted_surface_instead_of_falling_back_to_proof_job() -> None:
    def execute(request: search.SearchRequest) -> tuple[str, str, int]:
        return (
            "<html><title>Careers</title><p>Welcome to our careers page.</p></html>",
            request.url,
            200,
        )

    outcome = search.search_generic_origin(
        origin_url="https://example.test/careers",
        query="Data Engineer",
        execute=execute,
    )

    assert outcome.mechanism == "none"
    assert outcome.jobs == ()
    assert outcome.stop_reason == "no_deterministic_targeted_search_surface"
