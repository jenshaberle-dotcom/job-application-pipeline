from pathlib import Path

from src.connectors.stepstone_result_cards import (
    extract_result_card_fields,
    extract_stepstone_id_from_url,
    iter_article_blocks,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "stepstone_result_cards_sample.html"
FINAL_URL = "https://www.stepstone.de/jobs/data-engineer/in-hannover"


def load_fixture() -> str:
    return FIXTURE_PATH.read_text()


def test_iter_article_blocks_detects_only_result_cards() -> None:
    raw_html = load_fixture()

    blocks = iter_article_blocks(raw_html)

    assert len(blocks) == 2
    assert blocks[0].external_job_id == "123456"
    assert blocks[1].external_job_id == "222222"


def test_extract_result_card_fields_from_fixture() -> None:
    raw_html = load_fixture()

    cards = extract_result_card_fields(
        raw_html=raw_html,
        final_url=FINAL_URL,
    )

    assert len(cards) == 2

    first = cards[0]

    assert first.index == 1
    assert first.external_job_id == "123456"
    assert first.title == "Data Engineer (m/w/d)"
    assert first.company == "Example Data GmbH"
    assert first.location == "Hannover"
    assert first.detail_url == (
        "https://www.stepstone.de/stellenangebote--"
        "Data-Engineer-Hannover-Example-Data-GmbH--123456-inline.html"
    )
    assert first.raw_href == (
        "/stellenangebote--"
        "Data-Engineer-Hannover-Example-Data-GmbH--123456-inline.html"
    )
    assert first.title_id_matches_article_id is True

    assert first.publication_hint_text == "vor 2 Tagen"
    assert first.salary_hint_text is None
    assert first.salary_ui_prompt_text == "Gehalt anzeigen"
    assert first.remote_hint_text == "Teilweise Home-Office"
    assert first.employment_type_hint_text == "Vollzeit"

    assert "Python" in first.raw_card_text
    assert first.data_at_fields["job-item-title"] == "Data Engineer (m/w/d)"
    assert first.data_at_fields["job-item-company-name"] == "Example Data GmbH"
    assert first.data_at_fields["job-item-location"] == "Hannover"


def test_detects_mismatching_article_and_detail_url_ids() -> None:
    raw_html = load_fixture()

    cards = extract_result_card_fields(
        raw_html=raw_html,
        final_url=FINAL_URL,
    )

    second = cards[1]

    assert second.external_job_id == "222222"
    assert second.detail_url == (
        "https://www.stepstone.de/stellenangebote--"
        "Analytics-Engineer-Hannover-Example-Analytics-AG--333333-inline.html"
    )
    assert second.title_id_matches_article_id is False
    assert second.publication_hint_text == "Gestern"
    assert second.remote_hint_text == "Hybrid"


def test_global_detail_links_outside_result_cards_are_ignored() -> None:
    raw_html = load_fixture()

    cards = extract_result_card_fields(
        raw_html=raw_html,
        final_url=FINAL_URL,
    )

    parsed_urls = {card.detail_url for card in cards}

    assert (
        "https://www.stepstone.de/stellenangebote--"
        "Outside-Result-Card--999999-inline.html"
    ) not in parsed_urls


def test_extract_stepstone_id_from_url() -> None:
    assert (
        extract_stepstone_id_from_url(
            "https://www.stepstone.de/stellenangebote--"
            "Data-Engineer-Hannover-Example-Data-GmbH--123456-inline.html"
        )
        == "123456"
    )

    assert extract_stepstone_id_from_url(None) is None
    assert extract_stepstone_id_from_url("https://www.example.com/job/123456") is None
