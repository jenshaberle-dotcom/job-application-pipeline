from src.silver.relevance import (
    get_accessibility_matches,
    get_role_matches,
    get_skill_matches,
    is_relevant_for_silver,
)


def make_finanz_raw_job(title: str, profile_terms: list[str]) -> dict:
    return {
        "id": 10132,
        "source_name": "finanz_informatik:hannover",
        "source_url": "https://www.f-i.de/de/karriere/offene-stellen/hannover/example",
        "raw_data": {
            "source_family": "finanz_informatik",
            "source_target": "hannover",
            "result_card": {
                "title": title,
                "company_name": "Finanz Informatik GmbH & Co. KG",
                "location": "Hannover",
                "detail_url": "https://www.f-i.de/de/karriere/offene-stellen/hannover/example",
            },
            "job": {
                "title": title,
                "company_name": "Finanz Informatik GmbH & Co. KG",
                "location": "Hannover",
                "source_url": "https://www.f-i.de/de/karriere/offene-stellen/hannover/example",
                "profile_terms": profile_terms,
            },
            "detail_evidence": {
                "page_title": f"{title} - Finanz Informatik",
            },
        },
    }


def test_finanz_product_owner_candidate_is_relevant_for_silver() -> None:
    raw_job = make_finanz_raw_job(
        title="Product Owner OSPlus Versiegelung (m/w/d)",
        profile_terms=["data", "daten", "bi", "product owner"],
    )

    assert "product owner" in get_role_matches(raw_job)
    assert "hannover" in get_accessibility_matches(raw_job)
    assert is_relevant_for_silver(raw_job)


def test_finanz_software_entwickler_candidate_matches_hyphenated_role() -> None:
    raw_job = make_finanz_raw_job(
        title="Software-Entwickler (m/w/d)",
        profile_terms=["software", "entwickler", "data", "ki"],
    )

    assert "software entwickler" in get_role_matches(raw_job)
    assert "hannover" in get_accessibility_matches(raw_job)
    assert is_relevant_for_silver(raw_job)


def test_finanz_javascript_ui_candidate_uses_connector_profile_evidence() -> None:
    raw_job = make_finanz_raw_job(
        title="Java-Script und UI-Entwickler (m/w/d)",
        profile_terms=["javascript", "ui", "sql"],
    )

    assert "ui entwickler" in get_role_matches(raw_job)
    assert {"javascript", "java script", "ui"}.intersection(get_skill_matches(raw_job))
    assert "hannover" in get_accessibility_matches(raw_job)
    assert is_relevant_for_silver(raw_job)
