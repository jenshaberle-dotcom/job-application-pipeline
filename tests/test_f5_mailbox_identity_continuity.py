from src.search_intelligence.application_identity_matching import (
    ExistingApplicationIdentity,
    match_existing_application_identity,
)


def _identity(key: str, *, title: str | None, domain: str, thread: str | None = None):
    return ExistingApplicationIdentity(
        application_key=key,
        employer_name="Example",
        job_title=title,
        source_url=None,
        counterparty_domain=domain,
        thread_reference=thread,
    )


def test_exact_mailbox_thread_continues_identity_without_title() -> None:
    match = match_existing_application_identity(
        employer_name="Example",
        job_title=None,
        source_url=None,
        counterparty_domain="jobs.example",
        thread_reference="thread-1",
        applications=[_identity("app-1", title="AI Engineer", domain="jobs.example", thread="thread-1")],
    )
    assert match == ("app-1", False, "exact_mailbox_thread")


def test_unique_counterparty_domain_continues_identity_without_title() -> None:
    match = match_existing_application_identity(
        employer_name="Example",
        job_title=None,
        source_url=None,
        counterparty_domain="jobs.example",
        thread_reference="new-thread",
        applications=[_identity("app-1", title="AI Engineer", domain="jobs.example")],
    )
    assert match == ("app-1", False, "unique_counterparty_domain")


def test_multiple_applications_at_same_domain_do_not_guess_without_title() -> None:
    match = match_existing_application_identity(
        employer_name="Example",
        job_title=None,
        source_url=None,
        counterparty_domain="jobs.example",
        thread_reference="new-thread",
        applications=[
            _identity("app-1", title="AI Engineer", domain="jobs.example"),
            _identity("app-2", title="Data Engineer", domain="jobs.example"),
        ],
    )
    assert match == (None, True, "ambiguous_counterparty_domain")


def test_unique_domain_does_not_override_conflicting_job_title() -> None:
    existing = ExistingApplicationIdentity(
        application_key="hornet-data-engineer",
        employer_name="Hornetsecurity GmbH",
        job_title=(
            "Data Engineer - Germany - Hornetsecurity - "
            "Next-Gen Microsoft 365 Security"
        ),
        source_url=None,
        counterparty_domain="hornetsecurity.com",
        thread_reference=None,
    )

    match = match_existing_application_identity(
        employer_name="Hornetsecurity GmbH",
        job_title="AI Automation Architect - SDLC",
        source_url=None,
        counterparty_domain="hornetsecurity.com",
        thread_reference="new-hornet-thread",
        applications=[existing],
    )

    assert match == (None, False, None)


def test_unique_domain_with_matching_title_still_converges_via_company_title() -> None:
    existing = ExistingApplicationIdentity(
        application_key="continental-mlops",
        employer_name="Continental",
        job_title="(Senior) MLOps Engineer (m/f/d)",
        source_url=None,
        counterparty_domain="recruiting.continental.com",
        thread_reference=None,
    )

    match = match_existing_application_identity(
        employer_name="Continental",
        job_title="(Senior) MLOps Engineer (m/f/d)",
        source_url=None,
        counterparty_domain="recruiting.continental.com",
        thread_reference="new-continental-thread",
        applications=[existing],
    )

    assert match == (
        "continental-mlops",
        False,
        "exact_company_title_family",
    )
