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


def test_rejection_dominates_acknowledgement_language_in_same_message() -> None:
    result = classify_application_evidence(
        subject="Your application: AI Engineer / Data Scientist",
        text_excerpt=(
            "Thank you for your application. After careful review we regret to inform "
            "you that we have been unable to shortlist you."
        ),
        sender_domain="example.test",
    )

    assert result.candidate_class == "rejection"
    assert result.reason_code == "deterministic_rejection"
    assert result.confidence == 0.97


def test_bounded_rejection_signal_recovers_truncated_metadata_snippet() -> None:
    result = classify_application_evidence(
        subject="Capgemini - Rückmeldung zu deinem Bewerbungsprozess",
        text_excerpt=(
            "Hallo Jens, vielen Dank für deine Bewerbung für die Position als "
            "(Senior) Azure Data Engineer (w/m/d) sowie das entgegengebrachte Interesse"
        ),
        sender_domain="capgemini.com",
        deterministic_event_signals=("rejection",),
    )

    assert result.candidate_class == "rejection"
    assert result.reason_code == "deterministic_rejection"
    assert "bounded event signal: rejection" in result.matched_terms
    assert result.authority == "evidence_only"


def test_conflicting_high_impact_signals_still_require_review() -> None:
    result = classify_application_evidence(
        subject="Update zu Ihrer Bewerbung",
        text_excerpt="Vielen Dank für Ihre Bewerbung.",
        deterministic_event_signals=("offer_signal", "rejection"),
    )

    assert result.candidate_class == "ambiguous"
    assert result.reason_code == "multiple_deterministic_classes"
    assert result.confidence is None


def test_non_application_cancellation_is_not_rejection_evidence() -> None:
    result = classify_application_evidence(
        subject="Absage Coaching Session",
        text_excerpt="Ihre Coaching-Sitzung am Freitag wurde abgesagt.",
        sender_domain="coaching.example",
    )

    assert result.candidate_class == "other"
    assert result.reason_code == "no_deterministic_event_phrase"


def test_private_calendar_assessment_reminder_is_not_application_evidence() -> None:
    result = classify_application_evidence(
        subject="Benachrichtigung: Nach Assessment Termin im Mai schauen",
        text_excerpt="Termine für Urologie in den Kalender eingetragen.",
        sender_domain="google.com",
    )

    assert result.candidate_class == "other"
    assert result.reason_code == "no_deterministic_event_phrase"


def test_application_assessment_request_remains_detected() -> None:
    result = classify_application_evidence(
        subject="Assessment invitation for your application",
        text_excerpt="Please complete the assessment test for the position.",
        sender_domain="careers.example",
    )

    assert result.candidate_class == "assessment_request"
    assert result.reason_code == "deterministic_assessment_request"


def test_outbound_email_application_is_applied_observation_not_submission_authority() -> None:
    result = classify_application_evidence(
        subject="Bewerbung als Junior Data Engineer (m/w/d)",
        text_excerpt="Sehr geehrte Damen und Herren, anbei meine Bewerbung.",
        sender_domain="gmail.com",
        mail_direction="outbound",
        counterparty_domain="example-employer.com",
    )

    assert result.candidate_class == "application_acknowledgement"
    assert result.reason_code == "deterministic_outbound_application_sent"
    assert result.confidence == 0.99
    assert result.authority == "evidence_only"


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


def test_application_subject_with_role_and_employer_is_acknowledgement() -> None:
    result = classify_application_evidence(
        subject="Deine Bewerbung Data Engineer (m/w/d) bei Example Energy",
        text_excerpt=(
            "Vielen Dank für dein Interesse an einer Mitarbeit. "
            "Wir sichten deine Bewerbung für die Stelle Data Engineer."
        ),
        sender_domain="ats.example",
    )

    assert result.candidate_class == "application_acknowledgement"
    assert result.reason_code == "deterministic_application_acknowledgement"
    assert result.confidence == 0.95


def test_contextual_rejection_with_not_worked_out_phrase_is_detected() -> None:
    result = classify_application_evidence(
        subject="Rückmeldung zu Ihrer Bewerbung als Data Engineer",
        text_excerpt=(
            "Leider müssen wir Ihnen aber mitteilen, dass es dieses Mal "
            "nicht geklappt hat."
        ),
        sender_domain="jobs.example",
    )

    assert result.candidate_class == "rejection"
    assert result.reason_code == "deterministic_rejection"
    assert result.confidence == 0.97
