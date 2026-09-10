from src.search_intelligence.origin_surface_evidence import (
    extract_origin_surface_evidence,
    fingerprint_ats_url,
)


def test_fingerprints_known_ats_hosts_from_registry() -> None:
    workday = fingerprint_ats_url(
        "https://wd3.myworkdayjobs.com/HannoverRe_Careers"
    )
    personio = fingerprint_ats_url(
        "https://example.jobs.personio.de/job/123"
    )

    assert workday is not None
    assert workday.family == "workday"
    assert workday.public_feed_kind == "workday_cxs"
    assert personio is not None
    assert personio.family == "personio"
    assert personio.public_feed_kind == "personio_xml"


def test_extracts_canonical_and_attribute_bound_jobspace_links() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="/de/karriere/stellenangebote">
      <script>window.fake = 'https://evil.greenhouse.io/not-an-attribute';</script>
    </head><body>
      <a href="/karriere/jobs">Jobs</a>
      <iframe src="https://wd3.myworkdayjobs.com/Example_Careers"></iframe>
      <form action="https://jobs.example.org/careers/search"></form>
    </body></html>
    """

    evidence = extract_origin_surface_evidence(
        html=html,
        base_url="https://www.example.org/unternehmen",
    )

    assert evidence.canonical_url == "https://www.example.org/de/karriere/stellenangebote"
    assert "https://www.example.org/karriere/jobs" in evidence.jobspace_urls
    assert "https://wd3.myworkdayjobs.com/Example_Careers" in evidence.jobspace_urls
    assert "https://jobs.example.org/careers/search" in evidence.jobspace_urls
    assert [(item.family, item.source_attribute) for item in evidence.ats_fingerprints] == [
        ("workday", "iframe:src")
    ]


def test_arbitrary_page_text_never_becomes_ats_evidence() -> None:
    html = """
    <html><body>
      <p>Our recruiting team previously used greenhouse.io and Lever.</p>
      <script>const provider = 'https://boards.greenhouse.io/example';</script>
      <a href="/about">About</a>
    </body></html>
    """

    evidence = extract_origin_surface_evidence(
        html=html,
        base_url="https://example.org/",
    )

    assert evidence.ats_fingerprints == ()
    assert evidence.jobspace_urls == ()


def test_non_http_and_non_job_links_are_ignored() -> None:
    html = """
    <html><body>
      <a href="mailto:jobs@example.org">Mail us</a>
      <a href="javascript:void(0)">Click</a>
      <a href="/products">Products</a>
      <a href="https://jobs.lever.co/example">Jobs</a>
    </body></html>
    """

    evidence = extract_origin_surface_evidence(
        html=html,
        base_url="https://example.org/",
    )

    assert evidence.jobspace_urls == ("https://jobs.lever.co/example",)
    assert len(evidence.ats_fingerprints) == 1
    assert evidence.ats_fingerprints[0].family == "lever"
