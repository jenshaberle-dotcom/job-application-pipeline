from src.search_intelligence.application_event_classifier import (
    classify_application_evidence,
)


def test_rejection_phrase_is_evidence_only() -> None:
    result = classify_application_evidence(
        subject="Ihre Bewerbung",
        text_excerpt="Leider können wir Sie nicht berücksichtigen. Absage folgt.",
        sender_domain="example.test",
    )

    assert result.candidate_class == "rejection"
    assert result.reason_code == "deterministic_rejection"
    assert result.authority == "evidence_only"
    assert result.deterministic is True
    assert result.confidence == 0.97


def test_german_interview_invitation_is_detected() -> None:
    result = classify_application_evidence(
        subject="Einladung zum Vorstellungsgespräch",
        text_excerpt="Wir möchten Sie gern kennenlernen.",
        sender_domain="example.test",
    )

    assert result.candidate_class == "interview_invitation"
    assert result.authority == "evidence_only"


def test_conflicting_offer_and_rejection_requires_review() -> None:
    result = classify_application_evidence(
        subject="Update zu Ihrer Bewerbung",
        text_excerpt=(
            "Earlier we discussed a job offer. Leider können wir Sie nicht "
            "berücksichtigen."
        ),
    )

    assert result.candidate_class == "ambiguous"
    assert result.reason_code == "multiple_deterministic_classes"
    assert result.confidence is None
    assert result.authority == "evidence_only"


def test_empty_evidence_stays_ambiguous() -> None:
    result = classify_application_evidence(subject=None, text_excerpt=None)

    assert result.candidate_class == "ambiguous"
    assert result.reason_code == "insufficient_bounded_evidence"
    assert result.confidence is None


def test_sender_domain_without_event_phrase_is_other_not_lifecycle_truth() -> None:
    result = classify_application_evidence(
        subject="Kurze Rückfrage",
        text_excerpt="Können Sie uns Ihre Telefonnummer nennen?",
        sender_domain="example.test",
    )

    assert result.candidate_class == "other"
    assert result.reason_code == "no_deterministic_event_phrase"
    assert result.confidence == 0.40
    assert result.authority == "evidence_only"


def test_classifier_result_contains_no_state_mutation_authority() -> None:
    payload = classify_application_evidence(
        subject="Thank you for your application",
        text_excerpt="We have received your application.",
    ).as_payload()

    assert payload["candidate_class"] == "application_acknowledgement"
    assert payload["authority"] == "evidence_only"
    assert "application_state" not in payload
    assert "authoritative_stage" not in payload
    assert "transition" not in payload
