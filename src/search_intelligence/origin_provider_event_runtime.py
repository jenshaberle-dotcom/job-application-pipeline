"""Shared contracts for event-driven, provider-backed origin discovery.

The module intentionally contains no provider call and no mutation path. It
selects the bounded read-only database projection, derives a stable fingerprint
and validates the maximum provider request envelope used by the local dispatcher
and the private GitHub runtime.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from psycopg import Connection


IN_PROCESS_STATUSES = (
    "discovery",
    "manual_review_required",
    "connector_candidate",
    "build_approval_required",
    "registration_approval_required",
    "connector_validation_required",
)

RUNTIME_BOUNDARY = (
    "read_only_database_projection",
    "review_output_only_not_pipeline_input",
    "no_candidate_url_write",
    "no_connector_registration",
    "no_source_activation",
    "no_bronze_silver_write",
    "no_scheduler_change",
)


class OriginProviderRuntimeError(ValueError):
    """Raised when the bounded runtime contract cannot be satisfied."""


@dataclass(frozen=True)
class ProviderBudget:
    max_candidates: int = 6
    search_query_limit: int = 2
    search_max_results: int = 5
    max_provider_requests: int = 12

    def validate(self) -> "ProviderBudget":
        if self.max_candidates < 1:
            raise OriginProviderRuntimeError("max_candidates must be at least 1")
        if self.search_query_limit < 1:
            raise OriginProviderRuntimeError("search_query_limit must be at least 1")
        if not 1 <= self.search_max_results <= 10:
            raise OriginProviderRuntimeError("search_max_results must be between 1 and 10")
        if self.max_provider_requests < self.search_query_limit:
            raise OriginProviderRuntimeError(
                "max_provider_requests must permit at least one complete candidate"
            )
        return self

    @property
    def effective_candidate_limit(self) -> int:
        self.validate()
        provider_limited = self.max_provider_requests // self.search_query_limit
        return min(self.max_candidates, provider_limited)

    @property
    def planned_provider_requests(self) -> int:
        return self.effective_candidate_limit * self.search_query_limit

    def to_json(self) -> dict[str, int]:
        return {
            "max_candidates": self.max_candidates,
            "effective_candidate_limit": self.effective_candidate_limit,
            "search_query_limit": self.search_query_limit,
            "search_max_results": self.search_max_results,
            "max_provider_requests": self.max_provider_requests,
            "planned_provider_requests": self.planned_provider_requests,
        }


def normalize_company_keys(values: Sequence[str] | None) -> tuple[str, ...]:
    result: list[str] = []
    for raw in values or ():
        value = str(raw or "").strip()
        if value and value not in result:
            result.append(value)
    return tuple(result)


def _timestamp(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        current = value
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        return current.astimezone(timezone.utc).isoformat()
    return str(value)


def load_origin_benchmark_projection(
    conn: Connection[Any],
    *,
    limit: int,
    market_evidence_limit: int,
    company_keys: Sequence[str] | None = None,
    include_active_controlled: bool = False,
) -> list[dict[str, object]]:
    """Load only the fields required for change detection and origin discovery."""

    if limit < 1:
        raise OriginProviderRuntimeError("projection limit must be at least 1")
    if market_evidence_limit < 0:
        raise OriginProviderRuntimeError("market_evidence_limit must not be negative")

    guest_list = normalize_company_keys(company_keys)
    statuses = list(IN_PROCESS_STATUSES)
    if include_active_controlled:
        statuses.append("active_controlled")

    with conn.cursor() as cur:
        if guest_list:
            cur.execute(
                """
                SELECT DISTINCT ON (c.company_key)
                    c.id,
                    c.company_key,
                    c.company_name,
                    c.source_family_candidate,
                    c.status,
                    c.risk_level,
                    c.candidate_url,
                    c.updated_at
                FROM employer_origin_source_candidates c
                WHERE c.company_key = ANY(%s::text[])
                  AND (%s OR c.status <> 'active_controlled')
                ORDER BY
                    c.company_key,
                    c.updated_at DESC NULLS LAST,
                    c.id DESC
                """,
                (list(guest_list), include_active_controlled),
            )
            rows_by_key = {str(row["company_key"]): dict(row) for row in cur.fetchall()}
            candidate_rows = [rows_by_key[key] for key in guest_list if key in rows_by_key][
                :limit
            ]
        else:
            cur.execute(
                """
                SELECT DISTINCT ON (c.company_key)
                    c.id,
                    c.company_key,
                    c.company_name,
                    c.source_family_candidate,
                    c.status,
                    c.risk_level,
                    c.candidate_url,
                    c.updated_at
                FROM employer_origin_source_candidates c
                WHERE c.status = ANY(%s::text[])
                ORDER BY
                    c.company_key,
                    c.updated_at DESC NULLS LAST,
                    c.id DESC
                """,
                (statuses,),
            )
            candidate_rows = sorted(
                (dict(row) for row in cur.fetchall()),
                key=lambda row: (
                    _timestamp(row.get("updated_at")) or "",
                    int(row.get("id") or 0),
                ),
                reverse=True,
            )[:limit]

        selected_keys = [str(row["company_key"]) for row in candidate_rows]
        evidence_by_key: dict[str, list[str]] = {key: [] for key in selected_keys}
        if selected_keys and market_evidence_limit:
            cur.execute(
                """
                WITH ranked AS (
                    SELECT
                        normalized_company_key,
                        evidence_url,
                        row_number() OVER (
                            PARTITION BY normalized_company_key
                            ORDER BY observed_at DESC NULLS LAST, created_at DESC
                        ) AS evidence_rank
                    FROM market_evidence
                    WHERE normalized_company_key = ANY(%s::text[])
                      AND evidence_url IS NOT NULL
                )
                SELECT normalized_company_key, evidence_url
                FROM ranked
                WHERE evidence_rank <= %s
                ORDER BY normalized_company_key, evidence_rank
                """,
                (selected_keys, market_evidence_limit),
            )
            for row in cur.fetchall():
                key = str(row["normalized_company_key"])
                url = str(row.get("evidence_url") or "").strip()
                if key in evidence_by_key and url:
                    evidence_by_key[key].append(url)

    return [
        {
            "candidate_id": int(row["id"]),
            "company_key": str(row["company_key"]),
            "company_name": str(row.get("company_name") or ""),
            "source_family_candidate": str(row.get("source_family_candidate") or ""),
            "status": str(row.get("status") or ""),
            "risk_level": str(row.get("risk_level") or ""),
            "candidate_url": str(row.get("candidate_url") or ""),
            "updated_at": _timestamp(row.get("updated_at")),
            "market_evidence_urls": evidence_by_key.get(str(row["company_key"]), []),
        }
        for row in candidate_rows
    ]


def projection_fingerprint(projection: Sequence[Mapping[str, object]]) -> str:
    encoded = json.dumps(
        list(projection),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_dispatch_payload(
    *,
    pipeline_repository: str,
    pipeline_ref: str,
    fingerprint: str,
    budget: ProviderBudget,
    target_location: str,
    requested_at: str,
) -> dict[str, object]:
    """Build a metadata-only payload within repository_dispatch limits."""

    budget.validate()
    payload = {
        "schema_version": "origin_provider_dispatch.v1",
        "pipeline_repository": pipeline_repository,
        "pipeline_ref": pipeline_ref,
        "projection_fingerprint": fingerprint,
        "max_candidates": budget.max_candidates,
        "search_query_limit": budget.search_query_limit,
        "search_max_results": budget.search_max_results,
        "max_provider_requests": budget.max_provider_requests,
        "target_location": target_location,
        "requested_at": requested_at,
    }
    if len(payload) > 10:
        raise OriginProviderRuntimeError("repository_dispatch payload exceeds 10 fields")
    return payload
