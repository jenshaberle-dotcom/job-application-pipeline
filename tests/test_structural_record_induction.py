from src.search_intelligence.structural_record_induction import (
    induce_structural_record_navigation,
)


def test_repeated_job_cards_induce_observed_detail_navigation() -> None:
    html = """
    <main>
      <article class="job-card"><a href="/Vacancies/101/Description/2">Senior Data Engineer</a><span>Berlin · Vollzeit</span></article>
      <article class="job-card"><a href="/Vacancies/102/Description/2">Platform Engineer</a><span>Hamburg · Vollzeit</span></article>
      <article class="job-card"><a href="/Vacancies/103/Description/2">Cloud Architect</a><span>Hannover · Vollzeit</span></article>
    </main>
    """

    groups = induce_structural_record_navigation(
        page_url="https://jobs.example.com/Jobs/All",
        html=html,
        allowed_hosts={"jobs.example.com"},
        career_context_confirmed=True,
    )

    assert len(groups) == 1
    assert groups[0].signature == "article|class=job-card"
    assert groups[0].record_count == 3
    assert groups[0].distinct_navigation_count == 3
    assert groups[0].navigation_urls == (
        "https://jobs.example.com/Vacancies/101/Description/2",
        "https://jobs.example.com/Vacancies/102/Description/2",
        "https://jobs.example.com/Vacancies/103/Description/2",
    )
    assert groups[0].host_authority is False
    assert groups[0].product_authority is False


def test_repeated_job_signature_can_induce_observed_query_navigation() -> None:
    html = """
    <section class="jobs-list">
      <div class="job-row"><a href="/?action=view&id=alpha-101">Data Engineer</a><p>Berlin, Germany</p></div>
      <div class="job-row"><a href="/?action=view&id=beta-102">Data Analyst</a><p>Hamburg, Germany</p></div>
      <div class="job-row"><a href="/?action=view&id=gamma-103">ML Engineer</a><p>Hannover, Germany</p></div>
    </section>
    """

    groups = induce_structural_record_navigation(
        page_url="https://career.example.com/stellenangebote",
        html=html,
        allowed_hosts={"career.example.com"},
        career_context_confirmed=True,
    )

    assert len(groups) == 1
    assert groups[0].signature == "div|class=job-row"
    assert groups[0].distinct_navigation_count == 3
    assert all("action=view" in url for url in groups[0].navigation_urls)


def test_static_link_shared_by_records_is_removed_before_navigation_induction() -> None:
    html = """
    <article class="job-card"><a href="/jobs/101">Data Engineer</a><a href="/careers">Careers home</a><span>Berlin</span></article>
    <article class="job-card"><a href="/jobs/102">Platform Engineer</a><a href="/careers">Careers home</a><span>Hamburg</span></article>
    <article class="job-card"><a href="/jobs/103">Cloud Engineer</a><a href="/careers">Careers home</a><span>Hannover</span></article>
    """

    groups = induce_structural_record_navigation(
        page_url="https://www.example.com/careers/jobs",
        html=html,
        allowed_hosts={"www.example.com"},
        career_context_confirmed=True,
    )

    assert len(groups) == 1
    assert groups[0].navigation_urls == (
        "https://www.example.com/jobs/101",
        "https://www.example.com/jobs/102",
        "https://www.example.com/jobs/103",
    )


def test_navigation_chrome_is_not_treated_as_repeated_records() -> None:
    html = """
    <nav>
      <ul>
        <li class="job-menu"><a href="/jobs">Jobs overview navigation link</a></li>
        <li class="job-menu"><a href="/jobs/de">German jobs navigation link</a></li>
        <li class="job-menu"><a href="/jobs/en">English jobs navigation link</a></li>
      </ul>
    </nav>
    """

    assert induce_structural_record_navigation(
        page_url="https://www.example.com/careers",
        html=html,
        allowed_hosts={"www.example.com"},
        career_context_confirmed=True,
    ) == ()


def test_repeated_office_cards_do_not_become_job_navigation() -> None:
    html = """
    <div class="location-card"><a href="/locations/berlin">Berlin Office</a><p>Our office in Berlin Mitte</p></div>
    <div class="location-card"><a href="/locations/hamburg">Hamburg Office</a><p>Our office in Hamburg HafenCity</p></div>
    <div class="location-card"><a href="/locations/hannover">Hannover Office</a><p>Our office in Hannover Mitte</p></div>
    """

    assert induce_structural_record_navigation(
        page_url="https://www.example.com/careers",
        html=html,
        allowed_hosts={"www.example.com"},
        career_context_confirmed=True,
    ) == ()


def test_career_context_is_caller_owned_and_fail_closed() -> None:
    html = """
    <article class="job-card"><a href="/jobs/101">Data Engineer</a><span>Berlin</span></article>
    <article class="job-card"><a href="/jobs/102">Platform Engineer</a><span>Hamburg</span></article>
    <article class="job-card"><a href="/jobs/103">Cloud Engineer</a><span>Hannover</span></article>
    """

    assert induce_structural_record_navigation(
        page_url="https://www.example.com/",
        html=html,
        allowed_hosts={"www.example.com"},
        career_context_confirmed=False,
    ) == ()


def test_cross_host_links_are_not_induced_by_structural_record_layer() -> None:
    html = """
    <article class="job-card"><a href="https://jobs.external.test/jobs/101">Data Engineer</a><span>Berlin</span></article>
    <article class="job-card"><a href="https://jobs.external.test/jobs/102">Platform Engineer</a><span>Hamburg</span></article>
    <article class="job-card"><a href="https://jobs.external.test/jobs/103">Cloud Engineer</a><span>Hannover</span></article>
    """

    assert induce_structural_record_navigation(
        page_url="https://www.example.com/careers",
        html=html,
        allowed_hosts={"www.example.com"},
        career_context_confirmed=True,
    ) == ()
