from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

try:
    from src.normalization.company_keys import normalize_company_key
except ModuleNotFoundError:  # pragma: no cover - patch-context fallback; repo runtime has src.normalization.
    import re
    import unicodedata

    def normalize_company_key(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized.lower()).strip("_")
        for suffix in ("_gmbh", "_ag", "_se"):
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)]
        return normalized.strip("_")

SCHEMA_VERSION = "generic008.stop_control_evidence_registry.v1"
WORK_ITEM = "GENERIC-008 Stop-Control Evidence Registry"

STOP_CONTROL_GAPS = ("no_actionable_evidence_coverage", "negative_control_coverage")
SAFE_STOP_ACTIONS = frozenset(
    {
        "no_useful_external_hint_no_candidate_creation",
        "provider_auth_failed_requires_key_review",
        "probe_error_requires_retry_or_review",
    }
)
EXPLICIT_STOP_CONTROL_TYPES = frozenset(
    {
        "new_clean_no_actionable_negative_control",
        "existing_safe_stop_negative_control",
    }
)
ALLOWED_EVIDENCE_STRENGTHS = frozenset({"none", "provider_blocked", "probe_error", "safe_stop"})
BOUNDARY = "review_artifact_only_no_candidate_or_gate_write"
PLACEHOLDER_SUMMARY_PREFIX = "describe why no company-origin/detail/provider evidence"
ACCEPTED_STATUS = "accepted_for_benchmark"


@dataclass(frozen=True)
class StopControlEvidenceReviewInput:
    company_name: str
    evidence_summary: str
    reviewer: str
    review_date: str
    company_key: str | None = None
    control_type: str = "new_clean_no_actionable_negative_control"
    required_for_gap_ids: tuple[str, ...] = STOP_CONTROL_GAPS
    review_action: str = "no_useful_external_hint_no_candidate_creation"
    evidence_strength: str = "none"
    source_reference: str | None = None


@dataclass(frozen=True)
class StopControlEvidenceReviewPlan:
    schema_version: str
    generated_at_utc: str
    work_item: str
    insert_allowed: bool
    action: str
    reason: str
    row: Mapping[str, Any]
    safety_boundary: Mapping[str, bool]
    validation_errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["row"] = dict(self.row)
        data["safety_boundary"] = dict(self.safety_boundary)
        data["validation_errors"] = list(self.validation_errors)
        return data


def stop_control_registry_boundary() -> dict[str, bool]:
    return {
        "benchmark_review_artifact_only": True,
        "dry_run_by_default": True,
        "database_write_requires_explicit_write_flag": True,
        "database_write_scope_stop_control_evidence_reviews_only": True,
        "external_requests": False,
        "csv_excel_or_export_as_input": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_change": False,
        "bronze_silver_gold_mutation": False,
    }


def build_stop_control_evidence_review_plan(
    review_input: StopControlEvidenceReviewInput,
    *,
    generated_at: str | None = None,
) -> StopControlEvidenceReviewPlan:
    company_name = _text(review_input.company_name)
    company_key = _text(review_input.company_key) or normalize_company_key(company_name)
    control_type = _text(review_input.control_type)
    required_for_gap_ids = tuple(_unique(_text(value) for value in review_input.required_for_gap_ids))
    review_action = _text(review_input.review_action)
    evidence_strength = _text(review_input.evidence_strength, default="none")
    evidence_summary = _text(review_input.evidence_summary)
    reviewer = _text(review_input.reviewer)
    review_date = _text(review_input.review_date)
    source_reference = _text(review_input.source_reference) or None

    row = {
        "control_type": control_type,
        "required_for_gap_ids": list(required_for_gap_ids),
        "company_key": company_key,
        "company_name": company_name,
        "review_action": review_action,
        "evidence_strength": evidence_strength,
        "evidence_summary": evidence_summary,
        "reviewer": reviewer,
        "review_date": review_date,
        "boundary": BOUNDARY,
        "review_status": ACCEPTED_STATUS,
        "source_reference": source_reference,
        "evidence": {
            "decision_boundary": "benchmark_review_artifact_only_not_candidate_or_gate_truth",
            "evidence_origin": "operator_reviewed_stop_control_evidence",
        },
        "safety_boundary": stop_control_registry_boundary(),
    }
    errors = tuple(_validate_row(row))
    insert_allowed = not errors
    return StopControlEvidenceReviewPlan(
        schema_version=SCHEMA_VERSION,
        generated_at_utc=generated_at or datetime.now(timezone.utc).isoformat(),
        work_item=WORK_ITEM,
        insert_allowed=insert_allowed,
        action="insert_stop_control_evidence_review" if insert_allowed else "reject_invalid_stop_control_evidence_review",
        reason=(
            "explicit operator-reviewed stop-control evidence is ready for DB-backed benchmark use"
            if insert_allowed
            else "stop-control evidence review is incomplete or unsafe"
        ),
        row=row,
        safety_boundary=stop_control_registry_boundary(),
        validation_errors=errors,
    )


def insert_stop_control_evidence_review(conn: Any, plan: StopControlEvidenceReviewPlan) -> int:
    if not plan.insert_allowed:
        raise ValueError("stop-control evidence review is not insertable: " + ", ".join(plan.validation_errors))
    row = dict(plan.row)
    try:
        from psycopg.types.json import Jsonb

        row["evidence"] = Jsonb(row["evidence"])
        row["safety_boundary"] = Jsonb(row["safety_boundary"])
    except Exception:  # pragma: no cover - psycopg is available in runtime; keep tests import-light.
        pass
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stop_control_evidence_reviews (
                control_type,
                required_for_gap_ids,
                company_key,
                company_name,
                review_action,
                evidence_strength,
                evidence_summary,
                reviewer,
                review_date,
                boundary,
                review_status,
                source_reference,
                evidence,
                safety_boundary
            ) VALUES (
                %(control_type)s,
                %(required_for_gap_ids)s,
                %(company_key)s,
                %(company_name)s,
                %(review_action)s,
                %(evidence_strength)s,
                %(evidence_summary)s,
                %(reviewer)s,
                %(review_date)s,
                %(boundary)s,
                %(review_status)s,
                %(source_reference)s,
                %(evidence)s::jsonb,
                %(safety_boundary)s::jsonb
            )
            RETURNING id
            """,
            row,
        )
        inserted = cur.fetchone()
    if isinstance(inserted, Mapping):
        return int(inserted["id"])
    return int(inserted[0])


def fetch_accepted_stop_control_evidence_rows(conn: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
    limit_clause = ""
    params: dict[str, Any] = {"review_status": ACCEPTED_STATUS}
    if limit is not None:
        limit_clause = " LIMIT %(limit)s"
        params["limit"] = int(limit)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                control_type,
                array_to_string(required_for_gap_ids, ';') AS required_for_gap_ids,
                company_key,
                company_name,
                review_action,
                evidence_strength,
                evidence_summary,
                reviewer,
                review_date::text AS review_date,
                boundary
            FROM stop_control_evidence_reviews
            WHERE review_status = %(review_status)s
            ORDER BY created_at DESC, id DESC
            {limit_clause}
            """,
            params,
        )
        rows = cur.fetchall()
    return [_row_to_dict(row) for row in rows]


def render_plan_markdown(plan: StopControlEvidenceReviewPlan) -> str:
    row = dict(plan.row)
    lines = [
        "# GENERIC-008 Stop-Control Evidence Registry",
        "",
        f"- insert_allowed: `{plan.insert_allowed}`",
        f"- action: `{plan.action}`",
        f"- reason: `{plan.reason}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in plan.safety_boundary.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Review row", ""])
    for key in [
        "company_key",
        "company_name",
        "control_type",
        "required_for_gap_ids",
        "review_action",
        "evidence_strength",
        "evidence_summary",
        "reviewer",
        "review_date",
        "boundary",
    ]:
        lines.append(f"- {key}: `{row.get(key)}`")
    if plan.validation_errors:
        lines.extend(["", "## Validation errors", ""])
        for error in plan.validation_errors:
            lines.append(f"- {error}")
    lines.extend(["", "## Boundary", "", "This row is benchmark/control evidence only. It is not candidate creation, gate truth, connector activation, Bronze/Silver/Gold mutation, scheduler state, or an export-as-input handoff.", ""])
    return "\n".join(lines)


def _validate_row(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if row.get("control_type") not in EXPLICIT_STOP_CONTROL_TYPES:
        errors.append("control_type must be an explicit stop-control type")
    if set(STOP_CONTROL_GAPS) - set(_string_list(row.get("required_for_gap_ids"))):
        errors.append("required_for_gap_ids must include no_actionable_evidence_coverage and negative_control_coverage")
    if not _text(row.get("company_key")):
        errors.append("company_key is required")
    if not _text(row.get("company_name")):
        errors.append("company_name is required")
    if row.get("review_action") not in SAFE_STOP_ACTIONS:
        errors.append("review_action must be a safe-stop action")
    if row.get("evidence_strength") not in ALLOWED_EVIDENCE_STRENGTHS:
        errors.append("evidence_strength is not allowed")
    evidence_summary = _text(row.get("evidence_summary"))
    if not evidence_summary or evidence_summary.lower().startswith(PLACEHOLDER_SUMMARY_PREFIX):
        errors.append("evidence_summary must be explicit operator-written evidence, not a placeholder")
    if len(evidence_summary) < 40:
        errors.append("evidence_summary must be specific enough for audit review")
    if not _text(row.get("reviewer")):
        errors.append("reviewer is required")
    review_date = _text(row.get("review_date"))
    if not review_date:
        errors.append("review_date is required")
    else:
        try:
            date.fromisoformat(review_date)
        except ValueError:
            errors.append("review_date must be ISO date YYYY-MM-DD")
    if row.get("boundary") != BOUNDARY:
        errors.append(f"boundary must remain {BOUNDARY}")
    return errors


def _row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    # psycopg default tuple row order from fetch_accepted_stop_control_evidence_rows
    keys = [
        "control_type",
        "required_for_gap_ids",
        "company_key",
        "company_name",
        "review_action",
        "evidence_strength",
        "evidence_summary",
        "reviewer",
        "review_date",
        "boundary",
    ]
    return dict(zip(keys, row))


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = str(value).strip()
        key = item.lower()
        if item and key not in seen:
            out.append(item)
            seen.add(key)
    return out


def _text(value: Any, *, default: str = "") -> str:
    text = str(value).strip() if value is not None else ""
    return text or default
