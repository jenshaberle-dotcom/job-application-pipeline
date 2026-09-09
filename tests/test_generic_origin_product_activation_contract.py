from pathlib import Path


MIGRATION = Path(
    "db/migrations/107_create_generic_employer_origin_active_sources.sql"
)
ACTIVATION = Path("scripts/apply_generic_employer_origin_activation.py")
WORKFLOW = Path(".github/workflows/p1-generic-origin-product-activate.yml")


def test_generic_active_source_projection_accepts_only_canonical_pass_state() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "generic_employer_origin_active_sources" in sql
    assert "generic_evidence_driven_layer_model" in sql
    assert "CHECK (proof_state = 'pass')" in sql
    assert "source_name = 'generic_origin:' || company_key" in sql
    assert "employer_origin_candidate_gate_reviews" not in sql


def test_activation_uses_proof_projection_and_nonsemantic_wildcard_trigger() -> None:
    source = ACTIVATION.read_text(encoding="utf-8")

    assert 'GENERIC_AUTHORITY = "generic_evidence_driven_layer_model"' in source
    assert 'NEUTRAL_TRIGGER_TERM = "*"' in source
    assert "generic_employer_origin_active_sources" in source
    assert "connector_validation_gate" not in source
    assert "final_approval_gate" not in source


def test_main_activation_is_automatic_not_a_demo_or_manual_effect_path() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "push:" in workflow
    assert "branches: [main]" in workflow
    assert "workflow_dispatch" not in workflow
    assert "demo" not in workflow.casefold()
    assert "scripts.run_generic_employer_origin_product" in workflow
    assert "scripts.qualify_generic_employer_origin_connectors" in workflow
    assert "scripts.apply_generic_employer_origin_activation" in workflow
    assert "--source generic_origin" in workflow
