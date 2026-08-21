from __future__ import annotations

from src.connectors.employer_origin_form_navigation import (
    discover_strict_job_search_form_requests,
)


PAGE = "https://karriere.example.invalid/"
HOST = "karriere.example.invalid"


def test_discovers_same_host_post_filter_form_without_user_data() -> None:
    html = """
    <html><body>
      <form method="post" action="/">
        <input name="filter[text]" type="text" value="">
        <input name="filter[zip]" type="text" value="">
        <input name="scope" type="hidden" value="jobs">
        <button type="submit">Jobs suchen</button>
      </form>
    </body></html>
    """

    requests = discover_strict_job_search_form_requests(
        page_url=PAGE,
        html=html,
        allowed_hosts=(HOST,),
    )

    assert len(requests) == 1
    request = requests[0]
    assert request.url == "https://karriere.example.invalid"
    assert request.method == "POST"
    assert request.fields == (
        ("filter[text]", ""),
        ("filter[zip]", ""),
        ("scope", "jobs"),
    )


def test_login_and_application_forms_fail_closed() -> None:
    html = """
    <html><body>
      <form method="post" action="/login">
        <input name="username" type="text">
        <input name="password" type="password">
      </form>
      <form method="post" action="/jobs/apply">
        <input name="job" type="hidden" value="123">
        <input name="email" type="email">
        <input name="resume" type="file">
      </form>
    </body></html>
    """

    assert discover_strict_job_search_form_requests(
        page_url=PAGE,
        html=html,
        allowed_hosts=(HOST,),
    ) == ()


def test_cross_host_search_form_is_not_authorized_by_form_discovery() -> None:
    html = """
    <form method="post" action="https://other.example.invalid/jobs">
      <input name="filter[text]" type="text">
    </form>
    """

    assert discover_strict_job_search_form_requests(
        page_url=PAGE,
        html=html,
        allowed_hosts=(HOST,),
    ) == ()
