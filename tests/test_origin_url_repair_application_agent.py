from pathlib import Path

from scripts.run_origin_url_repair_application_agent import assess_repair_candidate


def test_assess_repair_candidate_accepts_public_https_career_url() -> None:
    result = assess_repair_candidate(
        company_key="adesso",
        company_name="adesso SE",
        repair_url="https://www.adesso.de/de/karriere/jobs/index.html",
    )

    assert result.repair_status == "repair_recommended"
    assert result.decision == "apply_repair_candidate_url"
    assert result.normalized_repair_url == "https://www.adesso.de/de/karriere/jobs/index.html"
    assert result.selected_source_type == "employer_origin_career_site"


def test_assess_repair_candidate_rejects_aggregator_url_for_manual_review() -> None:
    result = assess_repair_candidate(
        company_key="example",
        company_name="Example AG",
        repair_url="https://www.stepstone.de/jobs/example",
    )

    assert result.repair_status == "manual_review_required"
    assert result.decision == "manual_review_required"
    assert result.evidence["risk_level"] in {"medium", "blocked", "high"}


def test_apply_candidate_url_repair_uses_explicit_text_casts() -> None:
    script = Path("scripts/run_origin_url_repair_application_agent.py").read_text(encoding="utf-8")

    assert "candidate_url = %s::text" in script
    assert "COALESCE(%s::text, source_type_candidate)" in script
    assert "%s::text" in script
