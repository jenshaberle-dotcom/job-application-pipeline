from src.search_intelligence.official_domain_evidence import (
    WIKIDATA_API_URL,
    resolve_wikidata_official_domains,
)


def test_wikidata_p856_returns_bounded_provenance_rich_domain_candidates() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    def request_json(url: str, params: dict[str, str]) -> dict:
        calls.append((url, dict(params)))
        if params["action"] == "wbsearchentities":
            return {
                "search": [
                    {"id": "Q100"},
                    {"id": "Q200"},
                    {"id": "P999"},
                ]
            }
        assert params["action"] == "wbgetentities"
        return {
            "entities": {
                "Q100": {
                    "labels": {"de": {"value": "Beispiel AG"}},
                    "descriptions": {"de": {"value": "deutsches Unternehmen"}},
                    "claims": {
                        "P856": [
                            {
                                "mainsnak": {
                                    "datavalue": {"value": "https://www.beispiel.de"}
                                }
                            }
                        ]
                    },
                },
                "Q200": {
                    "labels": {"en": {"value": "Example Holdings"}},
                    "descriptions": {},
                    "claims": {
                        "P856": [
                            {
                                "mainsnak": {
                                    "datavalue": {"value": "https://example.com"}
                                }
                            },
                            {
                                "mainsnak": {
                                    "datavalue": {"value": "ftp://invalid.example"}
                                }
                            },
                        ]
                    },
                },
            }
        }

    evidence = resolve_wikidata_official_domains(
        "Beispiel AG",
        request_json=request_json,
        max_entities=3,
    )

    assert [item.url for item in evidence] == [
        "https://www.beispiel.de",
        "https://example.com",
    ]
    assert evidence[0].provider == "wikidata_p856"
    assert evidence[0].entity_id == "Q100"
    assert evidence[0].entity_label == "Beispiel AG"
    assert evidence[0].property_id == "P856"
    assert len(calls) == 2
    assert all(url == WIKIDATA_API_URL for url, _ in calls)
    assert calls[1][1]["ids"] == "Q100|Q200"


def test_wikidata_search_without_items_produces_no_domain_authority() -> None:
    calls = 0

    def request_json(url: str, params: dict[str, str]) -> dict:
        nonlocal calls
        calls += 1
        return {"search": []}

    assert resolve_wikidata_official_domains(
        "Unknown Company",
        request_json=request_json,
    ) == ()
    assert calls == 1
