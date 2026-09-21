from __future__ import annotations

from types import SimpleNamespace

from scripts.run_known_public_vacancy_parity import ba_company_matches, ba_matches, normalize, text_matches


def _record(*, title: str, employer: str, external_job_id: str = "10001-example-S"):
    return SimpleNamespace(
        raw_data={"job": {"titel": title, "arbeitgeber": employer}},
        source_url="https://example.test/job",
        external_job_id=external_job_id,
    )


def test_market_probe_text_matching_is_punctuation_insensitive() -> None:
    assert normalize("AI Automation Architect – Software Development Lifecycle") == (
        "ai automation architect software development lifecycle"
    )
    assert text_matches(
        "AI Automation Architect Software Development Lifecycle",
        "AI Automation Architect - Software Development Lifecycle - Germany",
    )


def test_ba_match_requires_title_and_employer() -> None:
    records = [
        _record(
            title="AI Automation Architect - Software Development Lifecycle",
            employer="Hornetsecurity GmbH",
        ),
        _record(title="AI Automation Architect", employer="Different GmbH"),
    ]

    matches = ba_matches(
        records,
        expected_company="Hornetsecurity",
        expected_title="AI Automation Architect Software Development Lifecycle",
    )

    assert len(matches) == 1
    assert matches[0].raw_data["job"]["arbeitgeber"] == "Hornetsecurity GmbH"


def test_ba_match_can_bind_exact_external_job_identity() -> None:
    records = [
        _record(
            title="AI Automation Architect - Software Development Lifecycle",
            employer="Hornetsecurity GmbH",
            external_job_id="10001-1003339347-S",
        ),
        _record(
            title="AI Automation Architect - Software Development Lifecycle",
            employer="Hornetsecurity GmbH",
            external_job_id="10001-other-S",
        ),
    ]

    matches = ba_matches(
        records,
        expected_company="Hornetsecurity",
        expected_title="AI Automation Architect Software Development Lifecycle",
        expected_external_job_id="10001-1003339347-S",
    )

    assert [record.external_job_id for record in matches] == ["10001-1003339347-S"]



def test_ba_company_match_does_not_require_sensor_job_identity() -> None:
    records = [
        _record(
            title="Different but relevant AI role",
            employer="Hornetsecurity GmbH",
            external_job_id="different-id",
        )
    ]

    matches = ba_company_matches(records, expected_company="Hornetsecurity")

    assert len(matches) == 1
