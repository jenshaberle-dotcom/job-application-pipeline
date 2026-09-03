from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORIGIN_GUARD = ROOT / "src/search_intelligence/product_v1_demo_origin_guard.py"
RUNTIME_ADAPTER = ROOT / "frontend/control-center/src/productPayloadRuntimeAdapter.ts"


def test_demo_scope_requires_current_employer_origin_truth_before_product_action() -> None:
    guard = ORIGIN_GUARD.read_text(encoding="utf-8")
    adapter = RUNTIME_ADAPTER.read_text(encoding="utf-8")

    assert '"active_confirmed"' in guard
    assert '"validated"' in guard
    assert '"stepstone"' in guard
    assert '"bundesagentur_fuer_arbeit"' in guard
    assert "aggregator_url_cannot_be_product_action_url" in guard
    assert "source_is_discovery_or_aggregator" in guard
    assert "allJobs.filter(demoActionable)" in adapter
    assert "discovery_job_readiness: allJobs" in adapter
