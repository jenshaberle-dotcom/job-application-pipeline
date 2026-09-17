from scripts.run_f5_candidate_supersession_schema_qualification import (
    PREREQUISITE_MIGRATION,
    TARGET_MIGRATION,
    TARGET_VIEW,
    QualificationStop,
    validate_report,
)


def test_candidate_supersession_qualification_targets_new_immutable_migration() -> None:
    assert TARGET_MIGRATION == "114_application_event_candidate_source_identity.sql"
    assert PREREQUISITE_MIGRATION == "113_enable_mailbox_first_application_tracking.sql"
    assert TARGET_VIEW == "gold_product_v1_application_tracking"


def test_candidate_supersession_report_requires_zero_mutation_boundaries() -> None:
    report = {
        "phase": "preflight",
        "source_sha": "abc",
        "boundaries": {
            "db_writes": 0,
            "gmail_reads": 0,
            "email_actions": 0,
            "application_submission_actions": 0,
            "authoritative_state_mutations": 0,
        },
    }
    validate_report(report, phase="preflight", source_sha="abc")

    report["boundaries"]["db_writes"] = 1
    try:
        validate_report(report, phase="preflight", source_sha="abc")
    except QualificationStop as exc:
        assert str(exc) == "BOUNDARY_NOT_ZERO:db_writes"
    else:
        raise AssertionError("mutation boundary must fail closed")
