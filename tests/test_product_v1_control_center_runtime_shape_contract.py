from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "frontend" / "control-center" / "src" / "main.tsx"
ADAPTER = ROOT / "frontend" / "control-center" / "src" / "productPayloadRuntimeAdapter.ts"
BOUNDARY = ROOT / "frontend" / "control-center" / "src" / "RuntimeErrorBoundary.tsx"
ASSESSMENT = ROOT / "src" / "search_intelligence" / "eon_product_v1_assessment.py"


def test_runtime_adapter_accepts_repository_backed_structured_evidence() -> None:
    assessment = ASSESSMENT.read_text(encoding="utf-8")
    adapter = ADAPTER.read_text(encoding="utf-8")

    # Repository-backed assessment truth stores explanations/uncertainties as
    # arrays of structured mappings, not string arrays.
    assert "explanations: tuple[Mapping[str, Any], ...]" in assessment
    assert "uncertainties: tuple[Mapping[str, Any], ...]" in assessment
    assert '"factor": "origin_validation"' in assessment
    assert '"action": "manual_review_required"' in assessment

    # The browser adapter must therefore render records deterministically rather
    # than passing raw objects through to React children.
    assert "function evidenceItemText(value: unknown): string" in adapter
    assert "const factor = compactValue(value.factor)" in adapter
    assert "const status = compactValue(value.status)" in adapter
    assert "const evidence = compactValue(value.evidence)" in adapter
    assert "const action = compactValue(value.action)" in adapter
    assert "explanations: normalizeEvidence(job.explanations)" in adapter
    assert "uncertainties: normalizeEvidence(job.uncertainties)" in adapter
    assert "job_readiness: normalizeJobs(value.job_readiness)" in adapter
    assert "top_jobs: normalizeJobs(value.top_jobs)" in adapter


def test_runtime_adapter_is_scoped_to_product_v1_get_payload() -> None:
    adapter = ADAPTER.read_text(encoding="utf-8")

    assert 'pathname === "/api/v1/product-v1"' in adapter
    assert "if (!response.ok || !isProductV1Request(input)) return response" in adapter
    assert 'headers.delete("content-length")' in adapter
    assert "response.clone().json()" in adapter


def test_control_center_installs_adapter_before_render_and_fails_visible() -> None:
    main = MAIN.read_text(encoding="utf-8")
    boundary = BOUNDARY.read_text(encoding="utf-8")

    install_index = main.index("installProductPayloadRuntimeAdapter();")
    render_index = main.index("createRoot(root).render")
    assert install_index < render_index
    assert "<RuntimeErrorBoundary>" in main
    assert "<App />" in main
    assert "<EvidencePreviewPanel />" in main

    assert "Control Center render failed" in boundary
    assert "frontend runtime" in boundary
    assert "window.location.reload()" in boundary
