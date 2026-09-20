from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "control-center" / "src"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_control_center_loads_product_truth_once_and_distributes_snapshot() -> None:
    main = read("main.tsx")
    context = read("ProductTruthContext.tsx")
    consumers = {
        "OperatorWorkspace.tsx": read("OperatorWorkspace.tsx"),
        "DemoProductPolish.tsx": read("DemoProductPolish.tsx"),
        "DemoApplicationWorkspace.tsx": read("DemoApplicationWorkspace.tsx"),
        "EvidencePreviewPanel.tsx": read("EvidencePreviewPanel.tsx"),
        "F4cSourceHealthSurface.tsx": read("F4cSourceHealthSurface.tsx"),
        "JobReviewLabelControls.tsx": read("JobReviewLabelControls.tsx"),
    }

    assert 'import { ProductTruthProvider } from "./ProductTruthContext";' in main
    assert "<ProductTruthProvider>" in main
    assert "readProductTruth<unknown>()" in context
    assert 'readProductTruth<unknown>({ fresh: true })' in context
    assert "refreshProductTruth" in context

    for name, source in consumers.items():
        assert 'from "./ProductTruthContext"' in source, name
        assert "readProductTruth" not in source, name
        assert 'fetch("/api/v1/product-v1"' not in source, name


def test_demo_polish_does_not_watch_whole_document_mutations() -> None:
    polish = read("DemoProductPolish.tsx")

    assert "MutationObserver" not in polish
    assert 'document.addEventListener("click", onClick)' in polish


def test_global_fetch_is_never_monkeypatched() -> None:
    main = read("main.tsx")
    adapter = read("productPayloadRuntimeAdapter.ts")

    assert "installProductPayloadRuntimeAdapter" not in main
    assert "window.fetch =" not in adapter
    assert "response.clone().json()" not in adapter
