from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "control-center" / "src"


def read(name: str) -> str:
    return (SRC / name).read_text(encoding="utf-8")


def test_initial_demo_components_share_one_product_truth_client() -> None:
    operator = read("OperatorWorkspace.tsx")
    polish = read("DemoProductPolish.tsx")
    application = read("DemoApplicationWorkspace.tsx")
    evidence = read("EvidencePreviewPanel.tsx")

    assert "readProductTruth<ProductPayload>()" in operator
    assert "readProductTruth<PolishPayload>()" in polish
    assert "readProductTruth<ProductTruth>()" in application
    assert "readProductTruth<ProductPayload>()" in evidence

    assert 'fetch("/api/v1/product-v1"' not in operator
    assert 'fetch("/api/v1/product-v1"' not in polish
    assert 'readJson<ProductTruth>("/api/v1/product-v1")' not in application
    assert 'fetch("/api/v1/product-v1"' not in evidence


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
