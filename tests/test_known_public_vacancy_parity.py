from __future__ import annotations

from types import SimpleNamespace

from scripts.run_known_public_vacancy_parity import ba_matches, normalize, text_matches


def _record(*, title: str, employer: str):
    return SimpleNamespace(
        raw_data={"job": {"titel": title, "arbeitgeber": employer}},
        source_url="https://example.test/job",
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
