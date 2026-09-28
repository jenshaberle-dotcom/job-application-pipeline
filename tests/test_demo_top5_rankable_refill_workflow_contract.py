from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "demo-top5-rankable-refill.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_demo_top5_refill_is_owner_only_and_exact_main_bound() -> None:
    text = _text()
    assert "github.event.issue.number == 1089" in text
    assert "github.event.comment.user.login == 'jenshaberle-dotcom'" in text
    assert "github.event.comment.author_association == 'OWNER'" in text
    assert "<!-- jap-demo-top5-refill:apply:v1 -->" in text
    assert "TOP5_APPROVAL_SOURCE_NOT_CURRENT_MAIN" in text
    assert 'test "$remote_main" = "$SOURCE_SHA"' in text


def test_demo_top5_refill_reuses_existing_guarded_authorities() -> None:
    text = _text()
    assert "scripts.run_demo_001_rankable_refill_scout" in text
    assert "scripts.run_demo_001_rankable_refill_campaign" in text
    assert "scripts.run_demo_001_rankable_refill_apply" not in text
    assert "DEMO-001-RANKABLE-REFILL-CAMPAIGN-001" in text
    assert "--apply" in text
    assert "hard_filter_operator_review_writes" in text
    assert "direct_rank_or_top5_writes" in text
    assert "TOP5_APPLY_HARD_FILTER_AUTHORITY_DRIFT" in text
    assert "TOP5_APPLY_DIRECT_RANK_AUTHORITY_DRIFT" in text


def test_demo_top5_refill_requires_real_five_job_result() -> None:
    text = _text()
    assert "TOP5_TARGET_MUST_BE_FIVE" in text
    assert "TOP5_TARGET_NOT_MET" in text
    assert "TOP5_VIEW_NOT_POPULATED" in text
    assert "rankable < target" in text
    assert "top_jobs < target" in text
    assert "payload.get(\"target_met\") is not True" in text


def test_demo_top5_refill_has_no_new_ranking_or_hard_filter_logic() -> None:
    text = _text()
    forbidden = (
        "UPDATE job_product_assessments",
        "INSERT INTO product_v1_capability_fit_reviews",
        "UPDATE product_v1_ranking_score_reviews",
        "INSERT INTO product_v1_ranking_score_reviews",
        "UPDATE gold_product_v1_top_jobs",
        "INSERT INTO gold_product_v1_top_jobs",
        "hard_filter_status = 'passed'",
    )
    for item in forbidden:
        assert item not in text


def test_demo_top5_refill_uses_readonly_preflights_before_apply() -> None:
    text = _text()
    scout = text.index("Scout real live Candidate-Fact-backed jobs")
    plan = text.index("Plan guarded refill campaign without writes")
    apply = text.index("Apply through existing revision capability hard-filter and ranking authorities")
    prove = text.index("Prove authoritative Top 5 result")
    post = text.index("Prove fit and Data Layers after refill")
    assert scout < plan < apply < prove < post
    assert text.count('PGOPTIONS="-c default_transaction_read_only=on"') >= 3
    assert "unset PGOPTIONS || true" in text



def test_demo_top5_refill_captures_postflight_product_and_data_layers_truth() -> None:
    text = _text()
    assert "scripts.run_f4a_profile_fit_diagnostic" in text
    assert "load_data_layers_payload" in text
    assert "TOP5_POST_PRODUCT_RANKABLE_LT_5" in text
    assert "TOP5_POST_PRODUCT_TOP_LT_5" in text
    assert "POST_GOLD_ASSESSED=" in text
    assert "POST_GOLD_FRESHNESS=" in text
    assert "/tmp/jap-demo-top5-data-layers-after.json" in text



def test_demo_top5_refill_reuses_verified_rcc_python_without_pypi_bootstrap() -> None:
    text = _text()

    assert "Resolve verified RCC runtime context" in text
    assert '"interpreter"' in text
    assert '"interpreter_probe"' in text
    assert "INTERPRETER_OUTSIDE_QUALIFIED_CHECKOUT" in text
    assert 'printf \'TOP5_PYTHON=%s\\n\'' in text
    assert "TOP5_RCC_PYTHON_IMPORTS=PASS" in text
    assert "import scripts.run_demo_001_rankable_refill_scout" in text
    assert "import scripts.run_demo_001_rankable_refill_campaign" in text

    assert "python3 -m venv" not in text
    assert "pip install --disable-pip-version-check -r requirements.txt" not in text
    assert "pip install --disable-pip-version-check --upgrade pip" not in text
