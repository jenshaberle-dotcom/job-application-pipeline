from src.search_intelligence.origin_source_discovery_agent import corporate_identity_aliases, corporate_identity_alias_tokens


def test_hannover_ruck_aliases_include_hannover_re() -> None:
    aliases = corporate_identity_aliases("hannover_ruck", "Hannover Rück SE")
    assert "hannover re" in aliases
    assert "hannover-re" in aliases


def test_eon_grid_aliases_include_eon() -> None:
    aliases = corporate_identity_aliases("e_on_grid_solutions", "E.ON Grid Solutions GmbH")
    assert "e.on" in aliases
    assert "eon" in aliases


def test_tib_aliases_include_short_brand() -> None:
    aliases = corporate_identity_aliases(
        "technische_informationsbibliothek_tib",
        "Technische Informationsbibliothek (TIB)",
    )
    assert "tib" in aliases


def test_hannover_ruck_alias_tokens_include_re() -> None:
    tokens = corporate_identity_alias_tokens("hannover_ruck", "Hannover Rück SE")
    assert "re" in tokens
