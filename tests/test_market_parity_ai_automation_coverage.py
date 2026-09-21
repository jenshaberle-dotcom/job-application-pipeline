from pathlib import Path


MIGRATION = Path("db/migrations/115_expand_ai_automation_market_coverage.sql")
WORKFLOW = Path(".github/workflows/p1-generic-origin-product-activate.yml")


def test_market_parity_migration_expands_ba_and_stepstone_with_generic_ai_terms() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "ba_data_engineer_30629_50km" in text
    assert "stepstone_data_engineer_hannover" in text
    for term in (
        "AI Architect",
        "AI Automation",
        "AI Automation Architect",
        "Agentic AI",
        "AI Governance",
    ):
        assert f"('{term}')" in text


def test_market_parity_seed_uses_first_party_origin_and_generic_authority_path() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "'hornetsecurity'" in text
    assert "'Hornetsecurity GmbH'" in text
    assert "'https://www.hornetsecurity.com/en/career/'" in text
    assert "'generic_origin:hornetsecurity'" in text
    assert "proof=PASS" in text
    assert "active_controlled" not in text


def test_activation_workflow_keeps_sensor_and_origin_authority_separate() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "--profile ba_data_engineer_30629_50km" in text
    assert "run_known_public_vacancy_parity" in text
    assert '--ba-search-term "AI Automation Architect"' in text
    assert "--ba-external-job-id" not in text
    for stage in (
        "ba_live",
        "sensor_company_evidence",
        "gold_canonical",
        "origin_candidate",
        "origin_active",
        "origin_raw",
        "origin_silver",
        "origin_gold",
    ):
        assert f"--require-stage {stage}" in text
    assert "--require-stage ba_raw" not in text
    assert "--require-stage ba_silver" not in text
    assert "--require-stage ba_gold" not in text
    assert "HORNET_TARGET_CONTROL_CENTER_PROJECTION=PASS" in text
    assert "MARKET_PARITY_REQUIRED_SOURCE_NOT_PROOF_PASS" not in text
