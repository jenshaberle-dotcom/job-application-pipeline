from pathlib import Path

from scripts.run_product_v1_f5_mailbox_silver_reconciliation_preflight import (
    build_tracking_job_linkage,
    classify_application,
    normalize_company,
    normalize_title,
)


SCRIPT = Path("scripts/run_product_v1_f5_mailbox_silver_reconciliation_preflight.py")


def _application(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": 1,
        "application_key": "mailbox-application:test",
        "silver_job_id": None,
        "job_identity_snapshot": {
            "employer_name": "Example GmbH",
            "job_title": "Data Engineer (m/w/d)",
            "application_url": None,
        },
    }
    row.update(overrides)
    return row


def _job(job_id: int, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "silver_job_id": job_id,
        "title": "Data Engineer",
        "company_name": "Example GmbH & Co. KG",
        "source_name": "generic_origin:example",
        "source_url": f"https://example.test/jobs/{job_id}",
        "lifecycle_status": "active_confirmed",
    }
    row.update(overrides)
    return row


def test_normalizers_handle_legal_suffix_and_gender_marker_noise() -> None:
    assert normalize_company("Example GmbH & Co. KG") == "example"
    assert normalize_company("Example GmbH") == "example"
    assert normalize_title("Data Engineer (m/w/d)") == "data engineer"
    assert normalize_title("Data Engineer") == "data engineer"
    assert normalize_title("E362/B - AI Engineer / KI-Entwickler (m/w/d)") == "e362 b ai engineer ki entwickler"
    assert normalize_title("Senior - Data Engineer") == "senior data engineer"


def test_exact_company_title_is_automatic_link_eligible() -> None:
    result = classify_application(_application(), [_job(42), _job(43, title="ML Engineer")])

    assert result["classification"] == "exact_company_title"
    assert result["automatic_link_eligible"] is True
    assert [row["silver_job_id"] for row in result["candidate_jobs"]] == [42]


def test_company_only_unique_match_requires_review() -> None:
    application = _application(
        job_identity_snapshot={
            "employer_name": "Valuny",
            "job_title": None,
            "application_url": None,
        }
    )
    result = classify_application(
        application,
        [_job(7, company_name="VALUNY GmbH", title="Machine Learning Engineer")],
    )

    assert result["classification"] == "review_company_exact_unique"
    assert result["automatic_link_eligible"] is False
    assert [row["silver_job_id"] for row in result["candidate_jobs"]] == [7]


def test_company_match_with_multiple_jobs_is_ambiguous() -> None:
    application = _application(
        job_identity_snapshot={
            "employer_name": "Example GmbH",
            "job_title": None,
            "application_url": None,
        }
    )
    result = classify_application(
        application,
        [_job(1), _job(2, title="ML Engineer")],
    )

    assert result["classification"] == "ambiguous_company"
    assert result["automatic_link_eligible"] is False
    assert [row["silver_job_id"] for row in result["candidate_jobs"]] == [1, 2]


def test_existing_link_is_never_reclassified_for_automatic_link() -> None:
    application = _application(silver_job_id=99)
    result = classify_application(application, [_job(99)])

    assert result["classification"] == "already_linked"
    assert result["automatic_link_eligible"] is False


def test_reconciliation_preflight_is_strictly_read_only() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert 'conn.execute("SET TRANSACTION READ ONLY")' in source
    assert '"database_writes": 0' in source
    assert '"gmail_network_requests": 0' in source
    assert '"application_submission_actions": 0' in source
    assert '"authoritative_lifecycle_mutations": 0' in source
    assert "INSERT INTO " not in source
    assert "UPDATE " not in source
    assert "DELETE FROM " not in source


def test_tracking_projection_surfaces_only_automatic_exact_matches() -> None:
    tracking = [
        {
            "application_id": 5,
            "silver_job_id": None,
            "company_name": "HDI",
            "display_company_name": "HDI",
            "title": "AI Engineer / Data Scientist",
            "source_url": None,
            "effective_stage": "closed",
        },
        {
            "application_id": 7,
            "silver_job_id": None,
            "company_name": "Capgemini",
            "display_company_name": "Capgemini",
            "title": "(Senior) Azure Data Engineer (w/m/d)",
            "source_url": None,
            "effective_stage": "closed",
        },
    ]
    jobs = [
        _job(
            2,
            company_name="HDI AG",
            title="AI Engineer / Data Scientist (m/w/d)",
        ),
        _job(
            483,
            company_name="Sogeti Part of Capgemini (Capgemini Deutschland GmbH)",
            title="(Senior) Cloud Engineer (w/m/d)",
        ),
    ]

    linkage = build_tracking_job_linkage(tracking, jobs)

    assert linkage["read_only"] is True
    assert linkage["exact_match_count"] == 1
    assert linkage["unresolved_count"] == 1
    assert linkage["database_writes"] == 0
    assert linkage["authoritative_lifecycle_mutations"] == 0
    assert linkage["exact_matches"] == [
        {
            "application_id": 5,
            "silver_job_id": 2,
            "effective_stage": "closed",
            "linkage_status": "exact_projected",
            "linkage_basis": "exact_company_title",
            "database_link_persisted": False,
        }
    ]


def test_specific_title_family_allows_embedded_location_suffix_but_short_generic_title_does_not() -> None:
    from src.search_intelligence.application_identity_matching import (
        strong_title_family_match,
    )

    assert strong_title_family_match(
        "AI Automation Architect Software Development Lifecycle",
        "AI Automation Architect Software Development Lifecycle Germany Europe",
    )
    assert not strong_title_family_match(
        "Data Engineer",
        "Senior Data Engineer Platform Germany",
    )


def test_finanz_informatik_mailbox_domain_plus_exact_vacancy_title_links_safely() -> None:
    tracking = [
        {
            "application_id": 18,
            "silver_job_id": None,
            "company_name": "f-i.de",
            "display_company_name": "f-i.de",
            "counterparty_domain": "f-i.de",
            "sender_domain": "f-i.de",
            "title": "E362/B - AI Engineer / KI-Entwickler (m/w/d)",
            "source_url": None,
            "effective_stage": "interview",
        }
    ]
    jobs = [
        _job(
            611,
            company_name="Finanz Informatik GmbH & Co. KG",
            title="AI Engineer / KI-Entwickler (m/w/d)",
        ),
        _job(
            630,
            company_name="Finanz Informatik GmbH & Co. KG",
            title="E362/B - AI Engineer / KI-Entwickler (m/w/d)",
        ),
    ]

    linkage = build_tracking_job_linkage(tracking, jobs)

    assert linkage["exact_matches"] == [
        {
            "application_id": 18,
            "silver_job_id": 630,
            "effective_stage": "interview",
            "linkage_status": "exact_projected",
            "linkage_basis": "exact_counterparty_domain_title",
            "database_link_persisted": False,
        }
    ]
    assert linkage["unresolved_count"] == 0



def test_finanz_informatik_real_current_title_without_mail_reference_prefix_links_safely() -> None:
    tracking = [
        {
            "application_id": 18,
            "silver_job_id": None,
            "company_name": "f-i.de",
            "display_company_name": "f-i.de",
            "counterparty_domain": "f-i.de",
            "sender_domain": "f-i.de",
            "title": "E362/B - AI Engineer / KI-Entwickler (m/w/d)",
            "source_url": None,
            "effective_stage": "interview",
        }
    ]
    jobs = [
        _job(
            611,
            company_name="Finanz Informatik GmbH & Co. KG",
            title="AI Engineer / KI-Entwickler (m/w/d)",
        )
    ]

    linkage = build_tracking_job_linkage(tracking, jobs)

    assert linkage["exact_matches"] == [
        {
            "application_id": 18,
            "silver_job_id": 611,
            "effective_stage": "interview",
            "linkage_status": "exact_projected",
            "linkage_basis": "exact_counterparty_domain_title_reference_normalized",
            "database_link_persisted": False,
        }
    ]
    assert linkage["unresolved_count"] == 0
