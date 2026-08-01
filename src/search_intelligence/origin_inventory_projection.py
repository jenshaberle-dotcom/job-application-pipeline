"""Project approved PostgreSQL observation evidence into SI-022A inputs.

The adapter is read-only and deterministic. It consumes the newest gate evidence
already stored for employer-origin candidates, validates the explicit
``origin_inventory_observation`` contract and calls the pure SI-022A resolver.
Missing or contradictory evidence becomes review output, never inferred truth.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from .origin_inventory_resolution import (
    ExternalJobSignal,
    OriginCandidateInventory,
    resolve_origin_inventory,
)


PROJECTION_SCHEMA_VERSION = "origin_inventory_projection.v1"
OBSERVATION_KEY = "origin_inventory_observation"
APPROVED_GATE_STATUSES = {"passed"}
APPROVED_GATE_DECISIONS = {
    "continue",
    "build_connector_candidate",
    "activate_controlled",
}
SOURCE_ROLE_BY_TYPE = {
    "employer_origin_career_site": "official_company",
    "employer_origin_ats_backed_career_site": "official_ats",
}

READ_ONLY_BOUNDARY: dict[str, bool] = {
    "read_only_transaction_required": True,
    "review_output_only_not_pipeline_input": True,
    "no_database_write": True,
    "no_proposal_table_write": True,
    "no_provider_call": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_scheduler_change": True,
    "no_candidate_or_gate_mutation": True,
}

CURRENT_OBSERVATION_QUERY = """
SELECT
    c.id AS candidate_id,
    c.company_key,
    c.company_name,
    c.candidate_url,
    c.source_family_candidate,
    c.source_target_candidate,
    c.source_type_candidate,
    c.status AS candidate_status,
    c.risk_level,
    latest_gate.gate_name,
    latest_gate.gate_status,
    latest_gate.decision,
    latest_gate.evidence,
    latest_gate.reviewed_at
FROM employer_origin_source_candidates AS c
LEFT JOIN LATERAL (
    SELECT
        gr.gate_name,
        gr.gate_status,
        gr.decision,
        gr.evidence,
        gr.reviewed_at,
        gr.updated_at
    FROM employer_origin_candidate_gate_reviews AS gr
    WHERE gr.candidate_id = c.id
    ORDER BY gr.reviewed_at DESC NULLS LAST, gr.updated_at DESC, gr.id DESC
    LIMIT 1
) AS latest_gate ON TRUE
ORDER BY c.company_key, c.id
""".strip()


@dataclass(frozen=True)
class ProjectionIssue:
    code: str
    message: str
    candidate_id: str | None = None
    field: str | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "candidate_id": self.candidate_id,
            "field": self.field,
        }


@dataclass(frozen=True)
class CompanyProjection:
    company_key: str
    company_name: str
    status: str
    candidate_count: int
    approved_observation_count: int
    issues: tuple[ProjectionIssue, ...]
    resolution: Mapping[str, object] | None

    def to_json(self) -> dict[str, object]:
        return {
            "company_key": self.company_key,
            "company_name": self.company_name,
            "status": self.status,
            "candidate_count": self.candidate_count,
            "approved_observation_count": self.approved_observation_count,
            "issues": [issue.to_json() for issue in self.issues],
            "resolution": None if self.resolution is None else dict(self.resolution),
        }


@dataclass(frozen=True)
class OriginInventoryProjection:
    as_of: date
    companies: tuple[CompanyProjection, ...]

    def to_json(self) -> dict[str, object]:
        resolved = sum(company.status == "resolved" for company in self.companies)
        return {
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "as_of": self.as_of.isoformat(),
            "company_count": len(self.companies),
            "resolved_company_count": resolved,
            "needs_inspection_company_count": len(self.companies) - resolved,
            "companies": [company.to_json() for company in self.companies],
            "boundary": READ_ONLY_BOUNDARY,
        }


def read_current_origin_observations(connection: Any) -> tuple[dict[str, Any], ...]:
    """Read the current candidate/gate projection inside a rolled-back transaction."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(CURRENT_OBSERVATION_QUERY)
            return tuple(dict(row) for row in cursor.fetchall())
    finally:
        connection.rollback()


def project_origin_observations(
    rows: Iterable[Mapping[str, Any]],
    *,
    as_of: date,
) -> OriginInventoryProjection:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        company_key = _text(row.get("company_key"))
        grouped[company_key].append(row)

    companies = tuple(
        _project_company(company_key, grouped[company_key], as_of=as_of)
        for company_key in sorted(grouped)
    )
    return OriginInventoryProjection(as_of=as_of, companies=companies)


def _project_company(
    company_key: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    as_of: date,
) -> CompanyProjection:
    issues: list[ProjectionIssue] = []
    company_names = {_text(row.get("company_name")) for row in rows}
    if not company_key:
        issues.append(
            ProjectionIssue("missing_company_key", "company_key is required", field="company_key")
        )
    if "" in company_names or len(company_names) != 1:
        issues.append(
            ProjectionIssue(
                "inconsistent_company_name",
                "company_name must be present and identical for all candidate rows",
                field="company_name",
            )
        )
    company_name = next(iter(company_names - {""}), "")

    candidates: list[OriginCandidateInventory] = []
    signals: list[ExternalJobSignal] = []
    failed_attempts: list[int] = []
    new_events: list[bool] = []
    for row in rows:
        candidate_id = _text(row.get("candidate_id")) or None
        observation, row_issues = _validated_observation(row, candidate_id=candidate_id)
        issues.extend(row_issues)
        if observation is None:
            continue
        try:
            candidates.append(_candidate_from_row(row, observation))
            signals.append(_external_signal(observation))
            failed_attempts.append(_required_int(observation, "failed_reobservation_attempt"))
            new_events.append(_required_bool(observation, "new_external_job_event"))
        except (TypeError, ValueError) as exc:
            issues.append(
                ProjectionIssue(
                    "invalid_observation_value",
                    str(exc),
                    candidate_id=candidate_id,
                )
            )

    signal = _single_consistent(signals, "external_job_signal", issues)
    failed_attempt = _single_consistent(
        failed_attempts,
        "failed_reobservation_attempt",
        issues,
    )
    new_event = _single_consistent(new_events, "new_external_job_event", issues)
    if issues or not candidates or signal is None or failed_attempt is None or new_event is None:
        return CompanyProjection(
            company_key=company_key,
            company_name=company_name,
            status="needs_inspection",
            candidate_count=len(rows),
            approved_observation_count=len(candidates),
            issues=tuple(issues or [ProjectionIssue("no_approved_observation", "no approved observation is available")]),
            resolution=None,
        )

    resolution = resolve_origin_inventory(
        company_key=company_key,
        company_name=company_name,
        candidates=tuple(candidates),
        external_job_signal=signal,
        as_of=as_of,
        failed_reobservation_attempt=failed_attempt,
        new_external_job_event=new_event,
    )
    return CompanyProjection(
        company_key=company_key,
        company_name=company_name,
        status="resolved",
        candidate_count=len(rows),
        approved_observation_count=len(candidates),
        issues=(),
        resolution=resolution.to_json(),
    )


def _validated_observation(
    row: Mapping[str, Any],
    *,
    candidate_id: str | None,
) -> tuple[Mapping[str, Any] | None, tuple[ProjectionIssue, ...]]:
    if row.get("gate_status") not in APPROVED_GATE_STATUSES or row.get("decision") not in APPROVED_GATE_DECISIONS:
        return None, (
            ProjectionIssue(
                "latest_gate_not_approved",
                "latest gate must be passed with an approved continuation decision",
                candidate_id=candidate_id,
                field="gate_status",
            ),
        )
    evidence = row.get("evidence")
    if not isinstance(evidence, Mapping):
        return None, (
            ProjectionIssue(
                "missing_gate_evidence",
                "latest gate evidence must be an object",
                candidate_id=candidate_id,
                field="evidence",
            ),
        )
    observation = evidence.get(OBSERVATION_KEY)
    if not isinstance(observation, Mapping):
        return None, (
            ProjectionIssue(
                "missing_origin_inventory_observation",
                f"evidence.{OBSERVATION_KEY} must be an object",
                candidate_id=candidate_id,
                field=f"evidence.{OBSERVATION_KEY}",
            ),
        )
    return observation, ()


def _candidate_from_row(
    row: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> OriginCandidateInventory:
    source_type = _text(row.get("source_type_candidate"))
    if source_type not in SOURCE_ROLE_BY_TYPE:
        raise ValueError(f"unsupported source_type_candidate: {source_type!r}")
    relevant_keys = observation.get("relevant_job_keys")
    if not isinstance(relevant_keys, Sequence) or isinstance(relevant_keys, (str, bytes)):
        raise TypeError("relevant_job_keys must be a list")
    return OriginCandidateInventory(
        candidate_id=_required_text(row, "candidate_id"),
        source_url=_required_text(row, "candidate_url"),
        source_role=SOURCE_ROLE_BY_TYPE[source_type],
        final_url=_optional_text(observation.get("final_url")),
        canonical_url=_optional_text(observation.get("canonical_url")),
        ats_tenant=_optional_text(observation.get("ats_tenant")),
        employer_scope=_optional_text(row.get("source_target_candidate")),
        reachable=_required_bool(observation, "reachable"),
        observed_job_count=_required_int(observation, "observed_job_count"),
        relevant_job_count=_required_int(observation, "relevant_job_count"),
        relevant_job_keys=tuple(str(value) for value in relevant_keys),
    )


def _external_signal(observation: Mapping[str, Any]) -> ExternalJobSignal:
    value = observation.get("external_job_signal")
    if not isinstance(value, Mapping):
        raise TypeError("external_job_signal must be an object")
    live = value.get("currently_live")
    if live is not None and not isinstance(live, bool):
        raise TypeError("external_job_signal.currently_live must be boolean or null")
    confidence = value.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise TypeError("external_job_signal.confidence must be numeric")
    return ExternalJobSignal(
        currently_live=live,
        confidence=float(confidence),
        observation_count=_required_int(value, "observation_count"),
        origin_miss_count=_required_int(value, "origin_miss_count"),
    )


def _single_consistent(values: Sequence[Any], field: str, issues: list[ProjectionIssue]) -> Any | None:
    if not values:
        return None
    first = values[0]
    if any(value != first for value in values[1:]):
        issues.append(
            ProjectionIssue(
                "contradictory_company_observation",
                f"{field} must be identical for all approved company observations",
                field=field,
            )
        )
        return None
    return first


def _required_text(value: Mapping[str, Any], field: str) -> str:
    text = _text(value.get(field))
    if not text:
        raise ValueError(f"{field} is required")
    return text


def _required_int(value: Mapping[str, Any], field: str) -> int:
    raw = value.get(field)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise TypeError(f"{field} must be an integer")
    if raw < 0:
        raise ValueError(f"{field} must not be negative")
    return raw


def _required_bool(value: Mapping[str, Any], field: str) -> bool:
    raw = value.get(field)
    if not isinstance(raw, bool):
        raise TypeError(f"{field} must be boolean")
    return raw


def _text(value: object) -> str:
    return str(value or "").strip()


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None
