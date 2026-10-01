from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RETIRED_GENERATION_PATHS = (
    "src/search_intelligence/product_v1_application_drafter.py",
    "src/search_intelligence/product_v1_application_drafter_quality.py",
    "src/search_intelligence/product_v1_application_quality_campaign.py",
    "src/search_intelligence/product_v1_evidence_first_draft.py",
    "scripts/run_product_v1_demo_draft_handoff.py",
)

ACTIVE_F6_AUTHORITY_PATHS = (
    "src/search_intelligence/product_v1_codex_application_adapter.py",
    "scripts/product_v1_application_workspace_runtime_quality.py",
    "scripts/product_v1_application_workspace_runtime.py",
    "scripts/run_product_v1_live_demo.py",
    "scripts/run_product_v1_demo_workspace_probe.py",
    "frontend/control-center/src/ApplicationWorkspace.tsx",
    "docs/planning/active/F6-TEMPLATE-AUTHORITATIVE-APPLICATION-DRAFTING.md",
)

BANNED_F6_AUTHORITY_MARKERS = (
    "5.6",
    "OPENAI_API_KEY",
    "JAP_CODEX_DRAFT_MODEL",
    "JAP_CODEX_REASONING_EFFORT",
    "deterministic_evidence_first",
    "provider_validated",
    "run_product_v1_demo_draft_handoff",
    "product_v1_application_drafter",
    "product_v1_application_drafter_quality",
    "product_v1_application_quality_campaign",
)


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_retired_application_generators_are_physically_absent() -> None:
    for relative in RETIRED_GENERATION_PATHS:
        assert not (ROOT / relative).exists(), relative


def test_active_f6_scope_contains_no_legacy_generation_authority() -> None:
    for relative in ACTIVE_F6_AUTHORITY_PATHS:
        text = _text(relative)
        for marker in BANNED_F6_AUTHORITY_MARKERS:
            assert marker not in text, f"{relative}: {marker}"


def test_f6_has_one_model_authority_and_one_quality_runtime() -> None:
    adapter = _text(
        "src/search_intelligence/product_v1_codex_application_adapter.py"
    )
    quality_runtime = _text(
        "scripts/product_v1_application_workspace_runtime_quality.py"
    )
    workspace_runtime = _text(
        "scripts/product_v1_application_workspace_runtime.py"
    )

    assert 'DEFAULT_MODEL = "gpt-6.1-sol"' in adapter
    assert '"evidence": "medium"' in adapter
    assert '"strategy": "high"' in adapter
    assert '"cv": "high"' in adapter
    assert '"letter": "high"' in adapter
    assert '"critic": "xhigh"' in adapter
    assert '"final": "high"' in adapter
    assert "request_codex_application_adaptation" in quality_runtime
    assert "no CV/letter generation authority" in workspace_runtime
    assert "generate_application_draft_payload" not in workspace_runtime
