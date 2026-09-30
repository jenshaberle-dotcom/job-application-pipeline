from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

GENERIC = (
    "run_product_v1_rankable_refill_scout.py",
    "run_product_v1_rankable_refill_apply.py",
    "run_product_v1_hard_filter_evidence_close.py",
    "run_product_v1_rankable_refill_campaign.py",
)


def _text(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_rankable_refill_has_one_canonical_product_chain() -> None:
    for name in GENERIC:
        assert (SCRIPTS / name).is_file()

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


def test_retired_compatibility_entrypoints_are_physically_absent() -> None:
    legacy_prefix = "run_" + "de" + "mo_001_"
    retired = (
        legacy_prefix + "rankable_refill_scout.py",
        legacy_prefix + "rankable_refill_apply.py",
        legacy_prefix + "rankable_refill_campaign.py",
        legacy_prefix + "rankable_refill_integrity.py",
        legacy_prefix + "hard_filter_evidence_close.py",
    )
    assert all(not (SCRIPTS / name).exists() for name in retired)


def test_assessment_cohort_uses_only_canonical_refill_authorities() -> None:
    source = _text("run_product_v1_assessment_cohort.py")

    assert "run_product_v1_rankable_refill_scout" in source
    assert "run_product_v1_rankable_refill_apply" in source
    assert "run_product_v1_rankable_refill_campaign" in source
