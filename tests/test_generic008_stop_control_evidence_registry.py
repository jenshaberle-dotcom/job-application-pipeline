from __future__ import annotations

from pathlib import Path

from src.search_intelligence.generic008_stop_control_evidence_registry import (
    BOUNDARY,
    StopControlEvidenceReviewInput,
    build_stop_control_evidence_review_plan,
    fetch_accepted_stop_control_evidence_rows,
    render_plan_markdown,
    stop_control_registry_boundary,
)


def _valid_input() -> StopControlEvidenceReviewInput:
    return StopControlEvidenceReviewInput(
        company_name="Clean Stop Control GmbH",
        evidence_summary="Bounded operator review found no actionable company-origin URL, detail page, or provider evidence after the reviewed search path.",
        reviewer="jens",
        review_date="2026-06-13",
        source_reference="manual bounded stop-control review",
    )


def test_plan_accepts_explicit_operator_stop_control_review() -> None:
    plan = build_stop_control_evidence_review_plan(_valid_input(), generated_at="2026-06-13T00:04:00+00:00")

    assert plan.schema_version == "generic008.stop_control_evidence_registry.v1"
    assert plan.insert_allowed is True
    assert plan.validation_errors == ()
    assert plan.row["company_key"] == "clean_stop_control"
    assert plan.row["boundary"] == BOUNDARY
    assert plan.safety_boundary["csv_excel_or_export_as_input"] is False
    assert plan.safety_boundary["candidate_creation"] is False
    assert plan.safety_boundary["database_write_scope_stop_control_evidence_reviews_only"] is True


def test_plan_rejects_placeholders_and_missing_review_fields() -> None:
    plan = build_stop_control_evidence_review_plan(
        StopControlEvidenceReviewInput(
            company_name="",
            evidence_summary="Describe why no company-origin/detail/provider evidence was actionable after bounded review.",
            reviewer="",
            review_date="not-a-date",
        )
    )

    assert plan.insert_allowed is False
    assert "company_key is required" in plan.validation_errors
    assert "company_name is required" in plan.validation_errors
    assert "evidence_summary must be explicit operator-written evidence, not a placeholder" in plan.validation_errors
    assert "reviewer is required" in plan.validation_errors
    assert "review_date must be ISO date YYYY-MM-DD" in plan.validation_errors


def test_markdown_states_hard_boundaries() -> None:
    plan = build_stop_control_evidence_review_plan(_valid_input())
    markdown = render_plan_markdown(plan)

    assert "GENERIC-008 Stop-Control Evidence Registry" in markdown
    assert "csv_excel_or_export_as_input" in markdown
    assert "not candidate creation" in markdown


def test_fetch_accepted_rows_maps_db_shape() -> None:
    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return [
                {
                    "control_type": "new_clean_no_actionable_negative_control",
                    "required_for_gap_ids": "no_actionable_evidence_coverage;negative_control_coverage",
                    "company_key": "clean_stop_control",
                    "company_name": "Clean Stop Control GmbH",
                    "review_action": "no_useful_external_hint_no_candidate_creation",
                    "evidence_strength": "none",
                    "evidence_summary": "Bounded review found no actionable origin/detail/provider evidence.",
                    "reviewer": "jens",
                    "review_date": "2026-06-13",
                    "boundary": BOUNDARY,
                }
            ]

    class Conn:
        def cursor(self):
            return Cursor()

    rows = fetch_accepted_stop_control_evidence_rows(Conn())

    assert rows[0]["company_key"] == "clean_stop_control"
    assert rows[0]["required_for_gap_ids"] == "no_actionable_evidence_coverage;negative_control_coverage"


def test_migration_creates_db_backed_registry_without_export_input() -> None:
    sql = Path("db/migrations/075_create_stop_control_evidence_reviews.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS stop_control_evidence_reviews" in sql
    assert "no CSV/Excel/export artifact as pipeline input" in sql
    assert "chk_stop_control_required_gaps" in sql
    assert "gold_stop_control_evidence_review_history" in sql
