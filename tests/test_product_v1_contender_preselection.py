from __future__ import annotations

from datetime import date

import pytest

from scripts.review_product_v1_contenders import positive_int
from src.search_intelligence.product_v1_contenders import (
    ProductV1ContenderRepository,
    build_contender_manifest,
    classify_geography,
    classify_role_title,
    exact_health_probe_eligible,
)


def row(
    silver_job_id: int,
    title: str,
    *,
    city: str | None = "Hannover",
    country: str | None = "DE",
    publication_date: date | None = date(2026, 8, 1),
    canonical_source_type: str | None = "employer_origin_career_site",
    source_url: str = "https://jobs.example.com/job/123/",
    work_model: str | None = None,
    commute_minutes: int | None = None,
    lifecycle_status: str = "stale_needs_refresh",
) -> dict:
    return {
        "silver_job_id": silver_job_id,
        "title": title,
        "company_name": f"Company {silver_job_id}",
        "city": city,
        "country": country,
        "publication_date": publication_date,
        "source_name": "example:discovery",
        "source_url": source_url,
        "canonical_source_type": canonical_source_type,
        "origin_validation_status": "validated",
        "work_model": work_model,
        "commute_minutes": commute_minutes,
        "lifecycle_status": lifecycle_status,
    }


@pytest.mark.parametrize(
    ("title", "tier"),
    [
        ("Machine Learning Engineer", "primary"),
        ("Senior MLOps Engineer", "primary"),
        ("ML Platform Engineer", "primary"),
        ("AI Platform Engineer", "primary"),
        ("Senior AI Research Engineer", "primary"),
        ("Cloud Data Engineer", "bridge"),
        ("Staff Engineer Data Platform", "bridge"),
        ("Analytics Engineer", "bridge"),
        ("AI Reliability Engineer", "primary"),
        ("Data Reliability Specialist", "strategic_probe"),
    ],
)
def test_approved_product_title_families_qualify(title: str, tier: str) -> None:
    signal = classify_role_title(title)
    assert signal is not None
    assert signal.tier == tier


@pytest.mark.parametrize(
    "title",
    [
        "Product Owner Data Platform",
        "Business Analyst",
        "Backend Engineer",
        "Cloud Engineer",
        "Software Engineer",
        "Data Scientist",
        "Power BI Platform Engineer",
    ],
)
def test_broad_silver_only_roles_do_not_qualify(title: str) -> None:
    assert classify_role_title(title) is None


def test_staff_engineer_data_platform_and_ai_is_primary_ai_probe() -> None:
    signal = classify_role_title("Staff Engineer Data Platform & Distributed AI")
    assert signal is not None
    assert signal.tier == "primary"
    assert "ai_engineer_probe" in signal.signals


def test_hannover_structured_city_is_best_geography_bucket() -> None:
    signal = classify_geography(row(1, "Data Engineer", country=None))
    assert signal.bucket == "hannover_explicit"
    assert signal.tier_order == 0
    assert signal.eligible_for_bounded_pool is True


def test_germany_remote_uses_existing_structured_assessment() -> None:
    signal = classify_geography(
        row(1, "Data Engineer", city="Berlin", country="Germany", work_model="remote")
    )
    assert signal.bucket == "germany_remote"
    assert signal.eligible_for_bounded_pool is True


def test_observed_commute_at_45_minutes_is_surfaced_not_invented() -> None:
    signal = classify_geography(
        row(1, "Data Engineer", city="Peine", commute_minutes=45)
    )
    assert signal.bucket == "commute_observed_acceptable"


def test_unknown_german_commute_requires_review_instead_of_acceptance_claim() -> None:
    signal = classify_geography(row(1, "Data Engineer", city="Berlin"))
    assert signal.bucket == "commute_or_geography_review_required"
    assert "no_approved_structured" in signal.reason


def test_structured_non_germany_is_excluded_from_product_lane() -> None:
    signal = classify_geography(
        row(1, "Data Engineer", city="Budapest", country="Hungary")
    )
    assert signal.bucket == "outside_germany"
    assert signal.eligible_for_bounded_pool is False


def test_exact_health_probe_requires_employer_origin_and_absolute_http_url() -> None:
    assert exact_health_probe_eligible(row(1, "Data Engineer")) is True
    assert (
        exact_health_probe_eligible(
            row(
                1,
                "Data Engineer",
                canonical_source_type="aggregator_company_discovery",
            )
        )
        is False
    )
    assert (
        exact_health_probe_eligible(
            row(1, "Data Engineer", source_url="/jobs/123")
        )
        is False
    )


def test_manifest_is_inspection_priority_not_ranking_and_preserves_stale_truth() -> None:
    rows = [
        row(
            1,
            "Product Owner Data Platform",
            lifecycle_status="stale_needs_refresh",
        ),
        row(
            2,
            "Data Engineer",
            city="Berlin",
            publication_date=date(2026, 8, 9),
        ),
        row(
            3,
            "AI Engineer",
            city="Hannover",
            lifecycle_status="stale_needs_refresh",
            publication_date=date(2026, 5, 1),
        ),
        row(
            4,
            "Machine Learning Engineer",
            city="Budapest",
            country="Hungary",
        ),
    ]

    manifest = build_contender_manifest(
        rows,
        transaction_read_only="on",
        limit=25,
    )

    assert manifest["counts"] == {
        "silver_inventory": 4,
        "role_preselected": 3,
        "structured_outside_germany_excluded": 1,
        "bounded_pool_before_limit": 2,
        "selected": 2,
    }
    assert [item["silver_job_id"] for item in manifest["rows"]] == [3, 2]
    assert manifest["rows"][0]["inspection_priority"] == 1
    assert manifest["rows"][0]["lifecycle_status"] == "stale_needs_refresh"
    assert manifest["rows"][0]["activity_claimed_by_preselection"] is False
    assert manifest["selection"]["ranking_score_created"] is False
    assert manifest["selection"]["freshness_ttl_applied"] is False
    assert manifest["boundary"]["database_writes"] is False
    assert manifest["boundary"]["network_requests"] is False


def test_inspection_order_prefers_role_then_geography_then_probe_then_publication() -> None:
    rows = [
        row(
            10,
            "Data Engineer",
            publication_date=date(2026, 8, 10),
        ),
        row(
            11,
            "AI Engineer",
            city="Berlin",
            publication_date=date(2026, 8, 10),
        ),
        row(
            12,
            "AI Engineer",
            city="Hannover",
            canonical_source_type="aggregator_company_discovery",
            publication_date=date(2026, 8, 10),
        ),
        row(
            13,
            "AI Engineer",
            city="Hannover",
            publication_date=date(2026, 7, 1),
        ),
        row(
            14,
            "AI Engineer",
            city="Hannover",
            publication_date=date(2026, 8, 1),
        ),
    ]

    manifest = build_contender_manifest(
        rows,
        transaction_read_only="on",
        limit=5,
    )
    assert [item["silver_job_id"] for item in manifest["rows"]] == [14, 13, 12, 11, 10]


def test_manifest_limit_is_bounded_and_positive() -> None:
    rows = [row(i, "Data Engineer") for i in range(1, 6)]
    manifest = build_contender_manifest(
        rows,
        transaction_read_only="on",
        limit=2,
    )
    assert manifest["counts"]["selected"] == 2

    with pytest.raises(ValueError, match="positive"):
        build_contender_manifest(rows, transaction_read_only="on", limit=0)


def test_manifest_refuses_non_read_only_transaction() -> None:
    with pytest.raises(ValueError, match="read_only"):
        build_contender_manifest([], transaction_read_only="off")


def test_cli_limit_validation_is_positive() -> None:
    assert positive_int("25") == 25
    with pytest.raises(Exception):
        positive_int("0")


class FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.statements: list[str] = []
        self.fetchone_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def fetchone(self) -> dict:
        self.fetchone_calls += 1
        return {"transaction_read_only": "on"}

    def fetchall(self) -> list[dict]:
        return self.rows


class FakeConnection:
    def __init__(self, rows: list[dict]) -> None:
        self.cursor_value = FakeCursor(rows)
        self.rollback_called = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self) -> FakeCursor:
        return self.cursor_value

    def rollback(self) -> None:
        self.rollback_called = True


def test_repository_enforces_read_only_before_inventory_select(monkeypatch) -> None:
    repository = ProductV1ContenderRepository()
    connection = FakeConnection([row(1, "Data Engineer")])
    monkeypatch.setattr(repository, "get_connection", lambda: connection)

    read_only, rows = repository.load_inventory_read_only()

    assert read_only == "on"
    assert len(rows) == 1
    assert connection.rollback_called is True
    assert connection.cursor_value.statements[0] == "SET TRANSACTION READ ONLY"
    assert connection.cursor_value.statements[1] == "SHOW transaction_read_only"
    assert "FROM gold_product_v1_job_readiness" in connection.cursor_value.statements[2]
