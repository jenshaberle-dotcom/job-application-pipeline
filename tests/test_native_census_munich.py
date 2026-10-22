import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.census_sources import munich
from src.census_sources.public_directory import links

FIXTURE = Path(__file__).parent / "fixtures/munich_startup_current_api.json"


def test_current_official_response_preserves_actual_names_websites_and_detail_identity():
    # Projection of GET /api/startups? observed 2026-10-09. The official list
    # bundle /_next/static/chunks/0jo8funuaqbu5.js uses this endpoint/cursor.
    # All descriptions, names of contacts, emails and phones were removed.
    value = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows, total, more, cursor = munich.parse_page(value)
    assert total == 1534 and more is True and cursor == "12"
    assert rows[0]["company_name"] == "Appdevelz"
    assert rows[0]["website"] == "https://www.appdevelz.com/"
    assert rows[0]["directory_url"] == "https://www.munich-startup.de/de/startups-and-ecosystem/appdevelz"
    assert rows[0]["source_record_id"] == "124733"
    assert rows[1]["company_name"] == "Fedcan" and rows[1]["website"] == "https://www.fedcan.de"
    assert not ({"email", "phone", "description", "founderCount"} & rows[0].keys())
    markup = FIXTURE.with_name("munich_startup_current_markup.html").read_text(encoding="utf-8")
    assert links(markup, munich.SOURCE.start_url) == [(rows[0]["directory_url"], rows[0]["company_name"])]


def pages():
    first = json.loads(FIXTURE.read_text(encoding="utf-8"))
    second = deepcopy(first)
    first.update(startups=first["startups"][:1], totalCount=2, cursor="1")
    second.update(startups=second["startups"][1:], totalCount=2, cursor=None, hasNextPage=False)
    return first, second


def test_pagination_uses_only_returned_cursor_and_verifies_terminal_count(monkeypatch):
    first, second = pages()
    fetch = Mock(side_effect=[json.dumps(first), json.dumps(second)])
    monkeypatch.setattr(munich, "fetch_text", fetch)
    result = munich.discover(delay=0)
    assert result["complete"] is True and result["company_count"] == 2
    assert [c.args[0] for c in fetch.call_args_list] == [munich.API + "?", munich.API + "?cursor=1"]
    assert len(result["pages"]) == 2 and all(len(p["response_sha256"]) == 64 for p in result["pages"])


@pytest.mark.parametrize("fault", ["repeated_cursor", "external_cursor", "missing_has_next", "limit"])
def test_unknown_pagination_never_succeeds_as_complete(monkeypatch, fault):
    first, second = pages()
    if fault == "repeated_cursor":
        second.update(hasNextPage=True, cursor="1")
    elif fault == "external_cursor":
        first["cursor"] = "https://private.test/"
    elif fault == "missing_has_next":
        first.pop("hasNextPage")
    else:
        monkeypatch.setattr(munich, "SOURCE", replace(munich.SOURCE, max_pages=1))
    fetch = Mock(side_effect=[json.dumps(first), json.dumps(second)])
    monkeypatch.setattr(munich, "fetch_text", fetch)
    with pytest.raises(ValueError):
        munich.discover(delay=0)
    assert fetch.call_count <= 2


def test_changed_reported_count_is_explicit_partial_observation(monkeypatch):
    first, second = pages()
    first["totalCount"] = 3  # Initial declared population is not fully observed.
    monkeypatch.setattr(munich, "fetch_text", Mock(side_effect=[json.dumps(first), json.dumps(second)]))
    result = munich.discover(delay=0)
    assert result["complete"] is False and result["reported_totals"] == [2, 3]
    assert result["company_count"] == 2


def test_later_page_counts_are_retained_without_replacing_initial_total(monkeypatch):
    first, second = pages()
    second["totalCount"] = 1
    monkeypatch.setattr(munich, "fetch_text", Mock(side_effect=[json.dumps(first), json.dumps(second)]))
    result = munich.discover(delay=0)
    assert result["complete"] is True and result["observed_directory_total"] == 2
    assert result["reported_totals"] == [1, 2]


def test_bad_optional_website_does_not_guess_employer_origin():
    first, _ = pages()
    first["startups"][0]["website"] = "https//www.finanzchef24.de"
    rows, *_ = munich.parse_page(first)
    assert rows[0]["website"] is None
