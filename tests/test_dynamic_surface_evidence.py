from src.search_intelligence.dynamic_surface_evidence import (
    extract_dynamic_route_literals,
    extract_html_dynamic_surface_evidence,
    same_host,
)


def test_html_dynamic_surface_collects_script_and_url_attributes() -> None:
    html = """
    <html><head><script src="/static/app.js"></script></head>
    <body>
      <div data-url="/api/jobs"></div>
      <a href="/about">About</a>
      <form action="/career/search"></form>
    </body></html>
    """
    evidence = extract_html_dynamic_surface_evidence(
        html=html,
        base_url="https://careers.example.test/",
    )
    assert evidence.script_sources == ("https://careers.example.test/static/app.js",)
    assert evidence.url_attributes == (
        "https://careers.example.test/api/jobs",
        "https://careers.example.test/career/search",
    )


def test_dynamic_literals_require_quoted_url_shape_and_job_or_api_marker() -> None:
    text = """
    const a='/api/jobs?lang=de';
    const b='/assets/logo.svg';
    const c='https://jobs.example.test/vacancies';
    const prose='we have many jobs available';
    """
    evidence = extract_dynamic_route_literals(
        text=text,
        base_url="https://careers.example.test/",
    )
    assert [item.normalized_url for item in evidence] == [
        "https://careers.example.test/api/jobs?lang=de",
        "https://jobs.example.test/vacancies",
    ]
    assert "job" in evidence[0].markers
    assert "vacanc" in evidence[1].markers


def test_dynamic_literal_extraction_is_bounded() -> None:
    text = "\n".join(f"const x{i}='/api/jobs/{i}';" for i in range(20))
    evidence = extract_dynamic_route_literals(
        text=text,
        base_url="https://careers.example.test/",
        max_literals=3,
    )
    assert len(evidence) == 3


def test_same_host_does_not_promote_cross_host_fetching() -> None:
    assert same_host(
        "https://careers.example.test/app.js",
        "https://careers.example.test/",
    )
    assert not same_host(
        "https://cdn.example.test/app.js",
        "https://careers.example.test/",
    )
