from pathlib import Path


def test_stepstone_company_discovery_cycle_script_keeps_boundaries_explicit() -> None:
    script = Path("scripts/run_stepstone_company_discovery_cycle_agent.py").read_text(encoding="utf-8")

    assert "dry-run first" in script
    assert "no pagination" in script
    assert "no detail pages" in script
    assert "no automatic candidate creation" in script
    assert "no connector activation" in script
    assert "no Bronze/Silver write" in script
    assert "no scheduler change" in script
    assert "--apply-cooldowns" in script
    assert "--write-review-state" in script
    assert "--seed-known-candidates" in script
    assert "--seed-market-evidence-companies" in script
    assert "skip_empty_exclusion_wave" in script


def test_stepstone_company_discovery_cycle_script_keeps_cooldown_application_explicit() -> None:
    script = Path("scripts/run_stepstone_company_discovery_cycle_agent.py").read_text(encoding="utf-8")

    assert "--review-id requires --apply-cooldowns" in script
    assert "temporary seed cooldowns" in script
    assert "not a permanent blacklist" in script
