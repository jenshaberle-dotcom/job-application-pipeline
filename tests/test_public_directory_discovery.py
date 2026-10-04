from src.search_intelligence.public_directory_discovery import DirectorySource, links, seed


def test_directory_primitives_resolve_links_and_preserve_dimensions():
    source = DirectorySource("x", "MUNICH", ("TECH",), "https://example.org/list")
    assert links('<a href="/company/acme">Acme GmbH</a>', source.start_url) == [
        ("https://example.org/company/acme", "Acme GmbH")
    ]
    row = seed("Acme GmbH", source, website="https://acme.example")
    assert row["geography"] == "MUNICH"
    assert row["cohorts"] == ["TECH"]
    assert row["source"] == "x"
