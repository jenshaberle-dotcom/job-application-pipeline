from pathlib import Path

SCRIPT = Path("scripts/run_origin_source_discovery_agent.py").read_text(encoding="utf-8")


def test_search_provider_choices_are_tavily_only_for_now() -> None:
    assert 'choices=("none", "tavily")' in SCRIPT


def test_env_loader_can_replace_placeholder_shell_value() -> None:
    assert "key not in os.environ or _is_missing_or_placeholder_secret(os.environ.get(key))" in SCRIPT


def test_disabled_legacy_providers_are_explicit() -> None:
    assert "provider_disabled_use_tavily" in SCRIPT
