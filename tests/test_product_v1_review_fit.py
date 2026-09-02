from src.search_intelligence.product_v1_review_fit import build_review_fit_preview


def _row(title: str, *, city: str = "Hannover", work_model: str = "unknown", lifecycle: str = "active_confirmed") -> dict[str, object]:
    return {
        "title": title,
        "city": city,
        "country": "Germany",
        "work_model": work_model,
        "commute_minutes": None,
        "lifecycle_status": lifecycle,
    }


def test_ml_engineer_remote_scores_as_primary_review_target() -> None:
    preview = build_review_fit_preview(
        _row("ML Engineer (m/f/d)", city="", work_model="remote")
    )

    assert preview.score >= 90
    assert preview.role_family == "machine_learning_engineer"
    assert preview.geography_bucket == "germany_remote"
    assert preview.ranking_authority is False
    assert preview.top5_authority is False


def test_ai_reliability_is_not_treated_as_generic_noise() -> None:
    preview = build_review_fit_preview(
        _row("AI Reliability Engineer", city="", work_model="remote")
    )

    assert preview.score >= 90
    assert preview.role_family == "ai_ml_data_reliability"


def test_data_engineer_remains_strong_bridge() -> None:
    preview = build_review_fit_preview(_row("Data Engineer"))

    assert preview.score >= 85
    assert preview.role_family == "data_engineer"


def test_outside_germany_fails_review_geography() -> None:
    row = _row("ML Engineer", city="London", work_model="unknown")
    row["country"] = "United Kingdom"
    preview = build_review_fit_preview(row)

    assert preview.score == 0
    assert preview.geography_bucket == "outside_germany"
