from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


DEFAULT_CONTENDER_LIMIT = 25
EMPLOYER_ORIGIN_SOURCE_TYPE = "employer_origin_career_site"


@dataclass(frozen=True)
class RoleSignal:
    tier: str
    tier_order: int
    family: str
    signals: tuple[str, ...]


@dataclass(frozen=True)
class GeographySignal:
    bucket: str
    tier_order: int
    eligible_for_bounded_pool: bool
    reason: str


class ProductV1ContenderRepository:
    def __init__(self) -> None:
        self.connection_config = get_database_config()

    def get_connection(self):
        return psycopg.connect(
            **self.connection_config,
            row_factory=dict_row,
        )

    def load_inventory_read_only(self) -> tuple[str, list[dict]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SHOW transaction_read_only")
                read_only = str(cur.fetchone()["transaction_read_only"])
                if read_only != "on":
                    raise RuntimeError("contender preselection requires read-only transaction")

                cur.execute(
                    "SELECT "
                    "silver_job_id, title, company_name, city, country, "
                    "publication_date, source_name, source_url, canonical_source_type, "
                    "origin_validation_status, work_model, commute_minutes, "
                    "lifecycle_status "
                    "FROM gold_product_v1_job_readiness "
                    "ORDER BY silver_job_id"
                )
                rows = [dict(row) for row in cur.fetchall()]

            conn.rollback()

        return read_only, rows


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    collapsed = re.sub(r"[^0-9a-z]+", " ", without_marks.casefold())
    return re.sub(r"\s+", " ", collapsed).strip()


def has_phrase(text: str, phrase: str) -> bool:
    return f" {normalize_text(phrase)} " in f" {normalize_text(text)} "


def classify_role_title(title: str) -> RoleSignal | None:
    text = normalize_text(title)

    if "reliability" in text and any(
        has_phrase(text, phrase)
        for phrase in ("ai", "ml", "machine learning", "data")
    ):
        return RoleSignal(
            tier="strategic_probe",
            tier_order=2,
            family="ai_ml_data_reliability",
            signals=("ai_ml_data_reliability",),
        )

    signals: list[str] = []
    if has_phrase(text, "mlops") or has_phrase(text, "ml ops"):
        signals.append("mlops")
    if "engineer" in text and (
        has_phrase(text, "machine learning") or has_phrase(text, "ml engineer")
    ):
        signals.append("machine_learning_engineer")
    if has_phrase(text, "ml platform") or has_phrase(text, "machine learning platform"):
        signals.append("ml_platform")
    if has_phrase(text, "ai platform"):
        signals.append("ai_platform")
    if "engineer" in text and (
        has_phrase(text, "ai") or has_phrase(text, "artificial intelligence")
    ):
        signals.append("ai_engineer_probe")

    if signals:
        return RoleSignal(
            tier="primary",
            tier_order=0,
            family=signals[0],
            signals=tuple(dict.fromkeys(signals)),
        )

    bridge_signals: list[str] = []
    if "engineer" in text and has_phrase(text, "data platform"):
        bridge_signals.append("data_platform_engineer")
    if has_phrase(text, "analytics engineer"):
        bridge_signals.append("analytics_engineer")
    if has_phrase(text, "data engineer"):
        bridge_signals.append("data_engineer")

    if bridge_signals:
        return RoleSignal(
            tier="bridge",
            tier_order=1,
            family=bridge_signals[0],
            signals=tuple(dict.fromkeys(bridge_signals)),
        )

    return None


def is_germany_country(value: object) -> bool:
    return normalize_text(value) in {"de", "deu", "deutschland", "germany"}


def classify_geography(row: dict) -> GeographySignal:
    city = normalize_text(row.get("city"))
    country = normalize_text(row.get("country"))
    work_model = normalize_text(row.get("work_model"))
    commute = row.get("commute_minutes")

    if country and not is_germany_country(country):
        return GeographySignal(
            bucket="outside_germany",
            tier_order=99,
            eligible_for_bounded_pool=False,
            reason="structured_country_outside_germany",
        )

    if city in {"hannover", "hanover"}:
        return GeographySignal(
            bucket="hannover_explicit",
            tier_order=0,
            eligible_for_bounded_pool=True,
            reason="structured_city_hannover",
        )

    if work_model == "remote" and is_germany_country(country):
        return GeographySignal(
            bucket="germany_remote",
            tier_order=1,
            eligible_for_bounded_pool=True,
            reason="existing_assessment_remote_with_germany_country",
        )

    if isinstance(commute, int) and commute <= 45:
        return GeographySignal(
            bucket="commute_observed_acceptable",
            tier_order=1,
            eligible_for_bounded_pool=True,
            reason="existing_commute_observation_at_or_below_45_minutes",
        )

    return GeographySignal(
        bucket="commute_or_geography_review_required",
        tier_order=2,
        eligible_for_bounded_pool=True,
        reason="no_approved_structured_hannover_remote_or_commute_evidence",
    )


def exact_health_probe_eligible(row: dict) -> bool:
    if row.get("canonical_source_type") != EMPLOYER_ORIGIN_SOURCE_TYPE:
        return False
    value = str(row.get("source_url") or "").strip()
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def publication_sort_key(value: object) -> int:
    if isinstance(value, datetime):
        return -value.date().toordinal()
    if isinstance(value, date):
        return -value.toordinal()
    if isinstance(value, str) and value.strip():
        try:
            return -date.fromisoformat(value[:10]).toordinal()
        except ValueError:
            pass
    return 0


def build_contender_manifest(
    rows: list[dict],
    *,
    transaction_read_only: str,
    limit: int = DEFAULT_CONTENDER_LIMIT,
) -> dict[str, object]:
    if transaction_read_only != "on":
        raise ValueError("transaction_read_only must be on")
    if limit <= 0:
        raise ValueError("limit must be a positive integer")

    candidates: list[tuple[dict, RoleSignal, GeographySignal, bool]] = []
    role_preselected_count = 0
    outside_germany_count = 0

    for row in rows:
        role = classify_role_title(str(row.get("title") or ""))
        if role is None:
            continue
        role_preselected_count += 1

        geography = classify_geography(row)
        if not geography.eligible_for_bounded_pool:
            outside_germany_count += 1
            continue

        candidates.append(
            (row, role, geography, exact_health_probe_eligible(row))
        )

    candidates.sort(
        key=lambda item: (
            item[1].tier_order,
            item[2].tier_order,
            0 if item[3] else 1,
            publication_sort_key(item[0].get("publication_date")),
            int(item[0]["silver_job_id"]),
        )
    )

    selected = candidates[:limit]
    output_rows: list[dict[str, object]] = []
    for priority, (row, role, geography, probe_eligible) in enumerate(
        selected,
        start=1,
    ):
        output_rows.append(
            {
                "inspection_priority": priority,
                "silver_job_id": int(row["silver_job_id"]),
                "title": row.get("title"),
                "company_name": row.get("company_name"),
                "city": row.get("city"),
                "country": row.get("country"),
                "publication_date": row.get("publication_date"),
                "role_tier": role.tier,
                "role_family": role.family,
                "role_signals": list(role.signals),
                "geography_bucket": geography.bucket,
                "geography_reason": geography.reason,
                "work_model": row.get("work_model"),
                "commute_minutes": row.get("commute_minutes"),
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "canonical_source_type": row.get("canonical_source_type"),
                "origin_validation_status": row.get("origin_validation_status"),
                "lifecycle_status": row.get("lifecycle_status"),
                "activity_claimed_by_preselection": False,
                "exact_health_probe_eligible": probe_eligible,
            }
        )

    return {
        "status": "product_v1_contender_preselection",
        "transaction_read_only": transaction_read_only,
        "purpose": "bounded_inspection_priority_only_not_ranking",
        "counts": {
            "silver_inventory": len(rows),
            "role_preselected": role_preselected_count,
            "structured_outside_germany_excluded": outside_germany_count,
            "bounded_pool_before_limit": len(candidates),
            "selected": len(output_rows),
        },
        "selection": {
            "limit": limit,
            "ranking_score_created": False,
            "freshness_ttl_applied": False,
            "activity_assumed_from_history": False,
        },
        "rows": output_rows,
        "boundary": {
            "database_writes": False,
            "network_requests": False,
            "provider_or_llm": False,
            "health_observation_writes": False,
            "assessment_or_hard_filter_writes": False,
            "candidate_fact_writes": False,
            "ranking_or_top5_writes": False,
            "application_writes": False,
        },
    }
