import json


def test_discovery_configs_cover_remaining_tech_geographies():
    geographies = set()
    for path in (
        "contracts/discovery/berlin-startup-map.json",
        "contracts/discovery/wolfsburg-innovations.json",
        "contracts/discovery/ingolstadt-digital.json",
    ):
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
        geographies.add(payload["geography"])
        assert payload["cohorts"] == ["TECH"]
        assert payload["start_url"].startswith("https://")
    assert geographies == {"BERLIN", "WOLFSBURG", "INGOLSTADT"}
