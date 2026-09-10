from src.search_intelligence.origin_vacancy_identity import (
    exact_origin_vacancy_identity,
    extract_explicit_vacancy_identifier,
)


def test_extracts_explicit_german_kennziffer() -> None:
    evidence = extract_explicit_vacancy_identifier(
        "Wir freuen uns auf Ihre Bewerbung unter Angabe der Kennziffer 392/B."
    )

    assert evidence is not None
    assert evidence.value == "392/B"
    assert evidence.normalized_value == "392/b"
    assert evidence.label == "kennziffer"


def test_extracts_common_explicit_job_identifiers() -> None:
    samples = {
        "Job ID: REQ-12345": "req-12345",
        "Requisition ID # JR_00842": "jr_00842",
        "Stellen-ID: DE-42/7": "de-42/7",
        "Job Reference: ABC-991": "abc-991",
    }

    for text, expected in samples.items():
        evidence = extract_explicit_vacancy_identifier(text)
        assert evidence is not None
        assert evidence.normalized_value == expected


def test_does_not_mine_unlabelled_numbers_or_generic_reference_copy() -> None:
    assert extract_explicit_vacancy_identifier(
        "Founded in 1992. More than 5000 employees at 3 locations."
    ) is None
    assert extract_explicit_vacancy_identifier(
        "See our reference architecture and ID management documentation."
    ) is None


def test_same_host_identifier_collapses_locale_url_aliases() -> None:
    first = exact_origin_vacancy_identity(
        origin_url="https://www.f-i.de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d",
        identifier="392/B",
    )
    second = exact_origin_vacancy_identity(
        origin_url="https://f-i.de/de/karriere/offene-stellen/frankfurt/data-platform-engineer-m-w-d",
        identifier="392/b",
    )

    assert first == second == ("f-i.de", "origin_vacancy_identifier", "392/b")


def test_same_identifier_on_different_origin_hosts_does_not_collapse() -> None:
    assert exact_origin_vacancy_identity(
        origin_url="https://jobs.example-a.de/jobs/42",
        identifier="REQ-42",
    ) != exact_origin_vacancy_identity(
        origin_url="https://jobs.example-b.de/jobs/42",
        identifier="REQ-42",
    )
