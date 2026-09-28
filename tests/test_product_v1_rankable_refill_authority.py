from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

GENERIC = (
    "run_product_v1_rankable_refill_scout.py",
    "run_product_v1_rankable_refill_apply.py",
    "run_product_v1_hard_filter_evidence_close.py",
    "run_product_v1_rankable_refill_campaign.py",
)
COMPAT = (
    "run_demo_001_rankable_refill_scout.py",
    "run_demo_001_rankable_refill_apply.py",
    "run_demo_001_rankable_refill_campaign.py",
)


def _text(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_generic_refill_authority_contains_no_demo_dependency() -> None:
    for name in GENERIC:
        source = _text(name)
        assert "run_demo_001_rankable_refill" not in source
        assert "demo_001_rankable_refill" not in source
        assert "DEMO_001_RANKABLE_REFILL" not in source
        assert "DEMO-001-RANKABLE-REFILL" not in source

    apply = _text("run_product_v1_rankable_refill_apply.py")
    assert "run_product_v1_rankable_refill_scout" in apply
    assert "run_product_v1_hard_filter_evidence_close" in apply
    assert "close_hard_filter_unknowns" in apply
    campaign = _text("run_product_v1_rankable_refill_campaign.py")
    assert "run_product_v1_rankable_refill_scout" in campaign
    assert "run_product_v1_rankable_refill_apply" in campaign

    scout = _text("run_product_v1_rankable_refill_scout.py")
    assert '"blocked_hard_filter": 3' in scout
    assert "'blocked_hard_filter'" in scout


def test_job_specific_demo_hard_filter_closer_is_physically_absent() -> None:
    assert not (SCRIPTS / "run_demo_001_hard_filter_evidence_close.py").exists()


def test_demo_entrypoints_are_compatibility_only() -> None:
    for name in COMPAT:
        source = _text(name)
        assert "Compatibility entrypoint for the retired DEMO-001" in source
        assert "No Product logic lives in this module." in source
        assert "run_product_v1_rankable_refill_" in source

    for forbidden in (
        "SELECT\n",
        "INSERT INTO",
        "UPDATE ",
        "fetch_exact_detail(",
        "apply_reviews(",
        "apply_item(",
    ):
        assert all(forbidden not in _text(name) for name in COMPAT)


def test_assessment_cohort_uses_only_canonical_generic_refill() -> None:
    source = _text("run_product_v1_assessment_cohort.py")
    assert "run_product_v1_rankable_refill_scout" in source
    assert "run_product_v1_rankable_refill_apply" in source
    assert "run_product_v1_rankable_refill_campaign" in source
    assert "run_demo_001_rankable_refill" not in source
