from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.finanz_informatik import (
    FinanzInformatikConnector,
    extract_candidate_links,
    select_detail_candidates,
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


def test_connector_builds_raw_record_from_bounded_fake_pages() -> None:
    listing_url = "https://www.f-i.de/de/karriere/offene-stellen"
    detail_url = "https://www.f-i.de/de/karriere/offene-stellen/hannover/product-owner-osplus-versiegelung-m-w-d"

    def fake_fetcher(url: str):
        if url == listing_url:
            return (
                f'<a href="{detail_url}">Product Owner OSPlus Versiegelung</a>',
                listing_url,
                200,
            )
        return (
            "<html><title>Product Owner OSPlus Versiegelung (m/w/d) - Finanz Informatik</title>"
            "<main>Product Owner Hannover SQL BI Daten</main>"
            "<nav>Duales Studium Ausbildung Trainee</nav></html>",
            detail_url,
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
    assert records[0].source_name == "finanz_informatik:hannover"
    assert records[0].raw_data["result_card"]["company_name"] == "Finanz Informatik GmbH & Co. KG"
    assert records[0].raw_data["detail_evidence"]["raw_html_persisted"] is False


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
