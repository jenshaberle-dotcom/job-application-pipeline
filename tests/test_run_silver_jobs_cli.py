from src.run_silver_jobs import resolve_source_patterns


def test_resolve_source_patterns_defaults_to_supported_sources() -> None:
    assert "enercity:%" in resolve_source_patterns(None)


def test_resolve_source_patterns_accepts_exact_enercity_source() -> None:
    assert resolve_source_patterns("enercity:discovery") == ["enercity:discovery"]


def test_resolve_source_patterns_accepts_enercity_family() -> None:
    assert resolve_source_patterns("enercity") == ["enercity:%"]
