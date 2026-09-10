from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.finanz_informatik import (
    FinanzInformatikConnector,
    extract_candidate_links,
    extract_detail_locations,
    select_detail_candidates,
    stable_external_job_id,
)


def test_extract_candidate_links_defers_secondary_location_without_remote() -> None:
    html = '<a href="/de/karriere/offene-stellen/frankfurt/business-analyst-m-w-d">Business Analyst</a>'

    candidates = extract_candidate_links(html, "https://www.f-i.de/de/karriere/offene-stellen")

    assert len(candidates) == 1
    assert candidates[0].recommendation == "defer_non_target_location_without_remote_signal"


def test_select_detail_candidates_keeps_only_target_scope() -> None:
    html = '''
        <a href="/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d">Product Owner</a>
        <a href="/de/karriere/offene-stellen/frankfurt/business-analyst-m-w-d">Business Analyst</a>
    '''

    candidates = extract_candidate_links(html, "https://www.f-i.de/de/karriere/offene-stellen")
    selected = select_detail_candidates(candidates, limit=3)

    assert [candidate.path for candidate in selected] == [
        "/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d"
    ]


def test_detail_location_learning_preserves_all_explicit_fi_cities() -> None:
    text = (
        "Für die Organisationseinheit Plattform analytische Daten suchen wir zum "
        "nächstmöglichen Termin für den Standort Hannover, Münster oder Frankfurt ein."
    )

    assert extract_detail_locations(text) == ("Hannover", "Münster", "Frankfurt")


def test_connector_builds_raw_record_from_bounded_fake_pages() -> None:
    listing_url = "https://www.f-i.de/de/karriere/offene-stellen"
    candidate_url = "https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d"
    final_detail_url = "https://www.f-i.de/de/karriere/offene-stellen/product-owner-osplus-versiegelung-m-w-d"

    def fake_fetcher(url: str):
        if url == listing_url:
            return (
                f'<a href="{candidate_url}">Product Owner OSPlus Versiegelung</a>',
                listing_url,
                200,
            )
        return (
            "<html><title>Product Owner OSPlus Versiegelung (m/w/d) - Finanz Informatik</title>"
            "<main>Product Owner SQL BI Daten. Standort Hannover, Münster oder Frankfurt.</main>"
            "<nav>Duales Studium Ausbildung Trainee</nav></html>",
            final_detail_url,
            200,
        )

    connector = FinanzInformatikConnector(fetcher=fake_fetcher)
    records, requested_url = connector.fetch_jobs(
        SearchProfile(
            id=1,
            profile_name="test",
            source_name="finanz_informatik:hannover",
            search_location=None,
            search_radius_km=None,
            offer_type=None,
            page_size=3,
        ),
        SearchTerm(search_term="*"),
    )

    assert requested_url == listing_url
    assert len(records) == 1
    record = records[0]
    assert record.source_name == "finanz_informatik:hannover"
    assert record.source_url == final_detail_url
    assert record.external_job_id == stable_external_job_id(final_detail_url)
    assert record.raw_data["result_card"]["company_name"] == "Finanz Informatik GmbH & Co. KG"
    assert record.raw_data["result_card"]["location"] == "Hannover; Münster; Frankfurt"
    assert [row["city"] for row in record.raw_data["job"]["locations"]] == [
        "Hannover",
        "Münster",
        "Frankfurt",
    ]
    assert record.raw_data["job"]["metadata"]["parser_family"] == "finanz_informatik_html_text_v1"
    assert record.raw_data["acquisition_boundary"]["structure_learning_before_bronze"] is True
    assert record.raw_data["detail_evidence"]["raw_html_persisted"] is False


def test_connector_collapses_listing_aliases_that_resolve_to_same_origin_vacancy() -> None:
    listing_url = "https://www.f-i.de/de/karriere/offene-stellen"
    hannover = "https://www.f-i.de/de/karriere/offene-stellen/hannover/ai-engineer-m-w-d"
    remote = "https://www.f-i.de/de/karriere/offene-stellen/remote/ai-engineer-m-w-d"
    canonical = "https://www.f-i.de/de/karriere/offene-stellen/ai-engineer-m-w-d"

    def fake_fetcher(url: str):
        if url == listing_url:
            return (
                f'<a href="{hannover}">AI Engineer Hannover</a>'
                f'<a href="{remote}">AI Engineer Remote</a>',
                listing_url,
                200,
            )
        return (
            "<html><title>AI Engineer / KI-Entwickler (m/w/d) - Finanz Informatik</title>"
            "<main>AI Python Daten. Standort Hannover. Remote und hybrid möglich.</main></html>",
            canonical,
            200,
        )

    records, _ = FinanzInformatikConnector(fetcher=fake_fetcher).fetch_jobs(
        SearchProfile(
            id=1,
            profile_name="test",
            source_name="finanz_informatik:hannover",
            search_location=None,
            search_radius_km=None,
            offer_type=None,
            page_size=3,
        ),
        SearchTerm(search_term="*"),
    )

    assert len(records) == 1
    assert records[0].source_url == canonical


def test_select_detail_candidates_excludes_student_roles_before_bounded_limit() -> None:
    html = '\n        <a href="/de/karriere/offene-stellen/hannover/werkstudierende-m-w-d-im-bereich-digitale-signatur-und-kasse">Werkstudierende (m/w/d) im Bereich Digitale Signatur und Kasse</a>\n        <a href="/de/karriere/offene-stellen/hannover/java-script-und-ui-entwickler-m-w-d">Java-Script und UI-Entwickler (m/w/d)</a>\n        <a href="/de/karriere/offene-stellen/hannover/werkstudierende-m-w-d-it-service-desk-1st-und-oder-2nd-level-service-institutsanbindungen">Werkstudierende (m/w/d) IT Service Desk - 1st und/oder 2nd Level Service Institutsanbindungen</a>\n        <a href="/de/karriere/offene-stellen/hannover/software-entwickler-m-w-d">Software-Entwickler (m/w/d)</a>\n        <a href="/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d">Product Owner OSPlus Versiegelung (m/w/d)</a>\n    '

    candidates = extract_candidate_links(html, "https://www.f-i.de/de/karriere/offene-stellen")
    selected = select_detail_candidates(candidates, limit=3)

    assert [candidate.path for candidate in selected] == [
        "/de/karriere/offene-stellen/hannover/java-script-und-ui-entwickler-m-w-d",
        "/de/karriere/offene-stellen/hannover/software-entwickler-m-w-d",
        "/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d",
    ]
    assert all("werkstudierende" not in candidate.path for candidate in selected)
