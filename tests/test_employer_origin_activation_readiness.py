from pathlib import Path


from scripts.review_employer_origin_activation_readiness import (
    ActiveProfile,
    candidate_from_raw_record,
    is_probable_job_detail_record,
    non_job_preview_records,
    summarize_overall_readiness,
)
from src.connectors.base import RawJobRecord


def raw_record(title: str, url: str, profile_terms: list[str]) -> RawJobRecord:
    return RawJobRecord(
        source_name="enercity:discovery",
        source_url=url,
        external_job_id=title.lower().replace(" ", "-"),
        raw_data={
            "job": {
                "title": title,
                "company_name": "enercity AG",
                "location": "Hannover",
                "source_url": url,
                "profile_terms": profile_terms,
            },
            "result_card": {
                "title": title,
                "company_name": "enercity AG",
                "location": "Hannover",
                "detail_url": url,
            },
        },
    )


def test_candidate_from_raw_record_uses_employer_origin_evidence() -> None:
    record = raw_record(
        "Cloud Infrastructure DevOps Engineer",
        "https://www.enercity.de/karriere/jobsuche/cloud-infrastructure-devops-engineer-J1",
        ["cloud", "azure"],
    )

    candidate = candidate_from_raw_record(record)

    assert candidate.source_candidate_url == record.source_url
    assert candidate.page_title == "Cloud Infrastructure DevOps Engineer"
    assert candidate.recommendation == "employer_origin_activation_readiness_record"
    assert candidate.matched_profile_terms == "cloud; azure"
    assert candidate.matched_location_terms == "Hannover"


def test_overall_readiness_blocks_without_final_approval() -> None:
    assert (
        summarize_overall_readiness(final_approval_passed=False, active_profiles=[], rows=[])
        == "activation_readiness_blocked_missing_final_approval"
    )


def test_overall_readiness_blocks_when_source_is_already_active() -> None:
    active = [ActiveProfile(profile_name="enercity_active", source_name="enercity:discovery", is_active=True)]

    assert (
        summarize_overall_readiness(final_approval_passed=True, active_profiles=active, rows=[])
        == "activation_readiness_blocked_already_active"
    )


def test_script_uses_shared_database_config() -> None:
    text = Path("scripts/review_employer_origin_activation_readiness.py").read_text(encoding="utf-8")

    assert "from src.config import get_database_config" in text
    assert "psycopg.connect(**get_database_config())" in text
    assert "os.environ[" not in text


def test_script_keeps_readiness_boundary() -> None:
    text = Path("scripts/review_employer_origin_activation_readiness.py").read_text(encoding="utf-8")

    assert '"database_writes": False' in text
    assert '"search_profile_created": False' in text
    assert '"source_activation_allowed": False' in text
    assert '"bronze_persistence_allowed": False' in text
    assert '"scheduler_change_allowed": False' in text


def test_script_reuses_shared_database_config_for_uniqueness_evidence() -> None:
    text = Path("scripts/review_employer_origin_activation_readiness.py").read_text(encoding="utf-8")

    assert "from psycopg.conninfo import make_conninfo" in text
    assert "def shared_database_dsn()" in text
    assert "make_conninfo(**get_database_config())" in text
    assert "load_database_evidence(shared_database_dsn())" in text
    assert "load_database_evidence(None)" not in text


def test_non_job_preview_records_detect_product_pages() -> None:
    job = raw_record(
        "Cloud Infrastructure DevOps Engineer",
        "https://www.enercity.de/karriere/jobsuche/cloud-infrastructure-devops-engineer-J1",
        ["cloud"],
    )
    product = raw_record(
        "Elektromobilität",
        "https://www.enercity.de/privatkunden/produkte/elektromobilitaet",
        ["data"],
    )

    assert is_probable_job_detail_record(job)
    assert not is_probable_job_detail_record(product)
    assert non_job_preview_records([job, product]) == [product]


def test_query_parameter_job_detail_reuses_s7n_safety_contract() -> None:
    origin_url = "https://karriere.example.com/de"
    job = raw_record(
        "Data Engineer (m/w/d)",
        "https://karriere.example.com/de?id=51980f",
        ["data"],
    )

    assert is_probable_job_detail_record(job, origin_url=origin_url)
    assert non_job_preview_records([job], origin_url=origin_url) == []


def test_query_parameter_job_detail_uses_trusted_record_evidence() -> None:
    origin_url = "https://karriere.example.com/de"
    url = "https://karriere.example.com/de?id=458ccb"
    job = RawJobRecord(
        source_name="example:discovery",
        source_url=url,
        external_job_id="de:example",
        raw_data={
            "job": {
                "title": "Details",
                "company_name": "Example GmbH",
                "location": "Deutschland",
                "source_url": url,
                "profile_terms": ["ai"],
            },
            "result_card": {
                "title": "Details",
                "company_name": "Example GmbH",
                "location": "Deutschland",
                "detail_url": url,
            },
            "detail_evidence": {
                "page_title": "Bid Manager (m/w/d) Enterprise Ausschreibungen",
            },
            "listing_evidence": {
                "listing_text": "Mehr erfahren",
            },
        },
    )

    assert candidate_from_raw_record(job).page_title == "Details"
    assert is_probable_job_detail_record(job, origin_url=origin_url)
    assert non_job_preview_records([job], origin_url=origin_url) == []


def test_query_parameter_job_detail_stays_blocked_with_only_generic_record_labels() -> None:
    origin_url = "https://karriere.example.com/de"
    url = "https://karriere.example.com/de?id=458ccb"
    generic = RawJobRecord(
        source_name="example:discovery",
        source_url=url,
        external_job_id="de:example",
        raw_data={
            "job": {"title": "Details"},
            "result_card": {"title": "Details"},
            "detail_evidence": {"page_title": "Karriere"},
            "listing_evidence": {"listing_text": "Mehr erfahren"},
        },
    )

    assert not is_probable_job_detail_record(generic, origin_url=origin_url)


def test_query_parameter_job_detail_fails_closed_without_trusted_origin() -> None:
    origin_url = "https://karriere.example.com/de"
    tracking = raw_record(
        "Data Engineer (m/w/d)",
        "https://karriere.example.com/de?utm_source=newsletter",
        ["data"],
    )
    unrelated = raw_record(
        "Data Engineer (m/w/d)",
        "https://jobs.example.net/de?id=51980f",
        ["data"],
    )
    generic = raw_record(
        "Details",
        "https://karriere.example.com/de?id=51980f",
        ["data"],
    )

    assert not is_probable_job_detail_record(tracking, origin_url=origin_url)
    assert not is_probable_job_detail_record(unrelated, origin_url=origin_url)
    assert not is_probable_job_detail_record(generic, origin_url=origin_url)


def test_overall_readiness_blocks_non_job_preview_records() -> None:
    assert (
        summarize_overall_readiness(
            final_approval_passed=True,
            active_profiles=[],
            rows=[],
            non_job_preview_count=1,
        )
        == "activation_readiness_blocked_non_job_preview_records"
    )
