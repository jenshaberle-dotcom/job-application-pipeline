from pathlib import Path


MIGRATION = Path("db/migrations/061_restore_employer_origin_gate_review_decision_vocabulary.sql")


def test_a1f_restores_non_passed_gate_review_decisions() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "employer_origin_candidate_gate_reviews_decision_check" in text
    assert "'passed'::text" in text
    assert "'abort_documented'::text" in text
    assert "'manual_review_required'::text" in text
    assert "'ready_for_final_approval'::text" in text
    assert "'approve_connector_registration'::text" in text


def test_a1f_gate_review_vocabulary_does_not_reintroduce_legacy_continue() -> None:
    text = MIGRATION.read_text(encoding="utf-8")

    assert "'continue'::text" not in text
    assert "'build_connector_candidate'::text" not in text
    assert "'activate_controlled'::text" not in text
