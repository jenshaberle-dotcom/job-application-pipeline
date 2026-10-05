"""Regressions for observed HSH tab/desktop/mobile structure, not an HTML capture.

Source: https://firmen.cc.hs-hannover.de/companies/page1/ (2026-10-05 web inspection).
The synthetic markup retains its repeated labels and company-profile link boundaries.
"""

from html import escape

import pytest

from scripts import discover_hannover_tech_hsh as module
from scripts.discover_hannover_tech_hsh import is_region, is_tech, parse_company_blocks


def card(identity=1, name="IBS GmbH", city="30163 Hannover", website="https://simu.example",
         fields=("Informationstechnologie", "Softwarentwicklung/-kenntnisse")):
    tabs = "".join(f"<li>{label}</li>" for label in
                   ("Berufsfeld(er)", "Anschrift", "Beschreibung", "Mitarbeitende", "Homepage"))
    field_html = "".join(f"<li>{escape(field)}</li>" for field in fields)
    return (f'<a href="/companies/{identity}/"><span>{escape(name)}</span></a>'
            f'<ul>{tabs}</ul><h3>Berufsfeld(er)</h3><ul>{field_html}</ul>'
            f'<h3>Anschrift</h3><div>{escape(city)}</div>'
            '<h3>Beschreibung</h3><p>Fixture description</p>'
            '<h3>Mitarbeitende</h3><div>1-50</div><h3>Homepage</h3>'
            f'<a href="{escape(website)}">{escape(website)}</a>'
            f'<div>Berufsfeld(er)</div><ul>{field_html}</ul>'
            f'<div>Anschrift</div><div>{escape(city)}</div>')


def test_parse_company_blocks_keeps_structured_directory_evidence():
    rows = parse_company_blocks(card(name="IBS - Ingenieurbuero fuer Bahnbetriebssysteme GmbH"))
    assert len(rows) == 1
    assert rows[0]["company_name"] == "IBS - Ingenieurbuero fuer Bahnbetriebssysteme GmbH"
    assert rows[0]["website"] == "https://simu.example"
    assert "Informationstechnologie" in rows[0]["fields"]
    assert rows[0]["source_record_id"].endswith("/companies/1/")


def test_region_and_tech_selection_are_explicit():
    assert is_region("Lister Straße 15, 30163 Hannover")
    assert is_region("31535 Neustadt am Rübenberge")
    assert not is_region("10117 Berlin")
    assert is_tech(["Informationstechnologie"])
    assert not is_tech(["Gesundheit & Soziale Dienste"])


def test_real_failure_shape_does_not_turn_tabs_or_urls_into_companies():
    table = ('<table><tr><th>Name</th><th>Berufsfeld(er)</th><th>Anschrift</th></tr>'
             '<tr><td><a href="/companies/1/">IBS GmbH</a></td>'
             '<td>Informationstechnologie</td><td>30163 Hannover</td></tr></table>')
    rows = parse_company_blocks(table + card() + card(2, "Social Org", "30827 Garbsen",
                               "https://social.example", ("Gesundheit & Soziale Dienste",)))
    assert [row["company_name"] for row in rows] == ["IBS GmbH", "Social Org"]
    assert [row["website"] for row in rows] == ["https://simu.example", "https://social.example"]
    assert len({row["source_record_id"] for row in rows}) == 2
    assert module.cohorts_for(rows[1]["fields"]) == ["SOCIAL"]


def test_repeated_record_views_do_not_duplicate_companies():
    assert len(parse_company_blocks(card() + card())) == 1


def test_same_name_different_profile_ids_preserve_both_records():
    rows = parse_company_blocks(card() + card(2, website="https://other.example"))
    assert len(rows) == 2
    assert rows[0]["source_record_id"] != rows[1]["source_record_id"]


def test_directory_identity_conflict_is_not_silently_overwritten():
    with pytest.raises(ValueError, match="directory_record_identity_conflict"):
        parse_company_blocks(card() + card(name="Different GmbH"))


def test_conflicting_mobile_address_fails_closed():
    with pytest.raises(ValueError, match="directory_record_field_conflict"):
        parse_company_blocks(card() + '<div>Anschrift</div><div>10117 Berlin</div>')


@pytest.mark.parametrize("href", ["/companies/page1/", "https://evil.example/companies/1/",
                                   "//evil.example/companies/1/", "javascript:alert(1)",
                                   "/companies/1/?q=x", "/companies/1/#x"])
def test_only_directory_company_links_are_identities(href):
    assert module.directory_identity(href) is None


def test_unlinked_fields_cannot_create_a_named_record():
    assert parse_company_blocks('<div>Homepage</div><div>Berufsfeld(er)</div>'
                                '<div>Informationstechnologie</div>') == []


def test_missing_homepage_does_not_inherit_next_company_website():
    rows = parse_company_blocks(card(website="") + card(2, "Other", website="https://other.example"))
    assert rows[0]["website"] == ""
    assert rows[1]["website"] == "https://other.example"


def test_hidden_script_markup_does_not_create_records():
    assert parse_company_blocks('<script>' + card() + '</script>') == []


def test_discover_preserves_identity_and_social_scope(monkeypatch):
    html = '<div>2 Firmen gefunden</div>' + card() + card(
        2, "Social Org", "30827 Garbsen", "https://social.example", ("Sozialwesen",))
    monkeypatch.setattr(module, "fetch_page", lambda *args: html)
    result = module.discover(1, 0, 10)
    assert result["company_count"] == 2
    assert result["pages_fetched"] == 1
    assert all(row["geography"] == "REGION_HANNOVER" for row in result["companies"])
    assert all(row["directory_url"] == row["source_record_id"] for row in result["companies"])
    assert {row["cohort"] for row in result["companies"]} == {"TECH", "SOCIAL"}


def test_positive_source_total_with_no_parsed_records_is_failure(monkeypatch):
    monkeypatch.setattr(module, "fetch_page", lambda *args: '<div>537 Firmen gefunden</div>')
    with pytest.raises(ValueError, match="directory_record_identity_not_found"):
        module.discover(1, 0, 10)


def test_explicit_empty_directory_can_return_zero(monkeypatch):
    monkeypatch.setattr(module, "fetch_page", lambda *args: '<div>0 Firmen gefunden</div>')
    assert module.discover(1, 0, 10)["company_count"] == 0


def test_footer_cannot_supply_a_second_company_address():
    html = card() + '<footer><p>Career Center</p><p>30459 Hannover</p></footer>'
    assert parse_company_blocks(html)[0]["location"] == "30163 Hannover"
