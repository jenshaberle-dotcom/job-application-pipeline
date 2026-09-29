from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ACTIVE_ROOTS = (
    ROOT / "src",
    ROOT / "scripts",
    ROOT / "frontend",
    ROOT / "windows",
    ROOT / ".github" / "workflows",
    ROOT / "docs" / "current",
    ROOT / "docs" / "reference",
    ROOT / "docs" / "planning" / "active",
    ROOT / "tests",
)

FORBIDDEN_AUTHORITY_TOKENS = (
    "DEMO-001",
    "demo_learning",
    "demo_cohort",
    "demo_generic_origin",
    "JAP_DEMO_CONNECTOR",
    "run_product_v1_live_demo",
    "run_product_v1_demo_",
    "run_demo_",
    "product_v1_demo_",
    "demo_actionable",
    "demo_actionability_reason",
    "demo_live_verified",
    "demo_live_reason",
    "demo-chain",
    "frozen demo cohort",
    "frozen_runtime_identity",
    "candidate_fit_required_count",
    "affinity_required_count",
)


def _active_files():
    for base in ACTIVE_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {
                ".py", ".ts", ".tsx", ".js", ".css", ".html", ".md", ".yml", ".yaml", ".json", ".cs", ".ps1", ".sh"
            }:
                yield path


def test_no_active_demo_named_files_remain() -> None:
    offenders = [
        str(path.relative_to(ROOT))
        for path in _active_files()
        if "demo" in path.name.casefold()
    ]
    assert offenders == []


def test_demo_only_authority_tokens_cannot_return_to_active_product_paths() -> None:
    offenders: list[str] = []
    for path in _active_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in FORBIDDEN_AUTHORITY_TOKENS:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)}::{token}")
    assert offenders == []
