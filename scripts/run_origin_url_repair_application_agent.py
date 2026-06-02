"""Apply reviewed origin URL repairs from the S7O build candidate queue.

Boundary: this helper may update employer_origin_source_candidates.candidate_url
when --write is passed and the repair URL passes the existing origin-source URL
safety policy. It does not build connector artifacts, register connectors,
activate sources, write Bronze records or change schedules.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Any, Sequence

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.origin_source_discovery import (
    CandidateUrlEvidence,
    assess_url,
    auto_assignment_allowed_for_assessment,
)

BOUNDARY = {
    "no_connector_artifact_generation": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_write": True,
    "no_scheduler_change": True,
    "no_candidate_promotion": True,
}


@dataclass(frozen=True)
class RepairAssessment:
    repair_status: str
    decision: str
    normalized_repair_url: str | None
    selected_source_type: str | None
    reason: str
    evidence: dict[str, Any]


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def assess_repair_candidate(*, company_key: str, company_name: str, repair_url: str) -> RepairAssessment:
    assessed = assess_url(
        CandidateUrlEvidence(
            url=repair_url,
            evidence_source="s7p_reviewed_origin_url_repair_candidate",
            source_priority=1,
            evidence={"company_key": company_key, "company_name": company_name},
        )
    )
    allowed, allowed_reason = auto_assignment_allowed_for_assessment(assessed)
    evidence = {
        "input_url": assessed.input_url,
        "normalized_url": assessed.normalized_url,
        "domain": assessed.domain,
        "source_type": assessed.source_type,
        "safe_to_probe_later": assessed.safe_to_probe_later,
        "confidence_score": assessed.confidence_score,
        "risk_level": assessed.risk_level,
        "url_decision": assessed.decision,
        "url_reasons": list(assessed.reasons),
        "auto_assignment_allowed": allowed,
        "auto_assignment_reason": allowed_reason,
    }
    if allowed and assessed.normalized_url:
        return RepairAssessment(
            repair_status="repair_recommended",
            decision="apply_repair_candidate_url",
            normalized_repair_url=assessed.normalized_url,
            selected_source_type=assessed.source_type,
            reason="Repair candidate is public HTTPS career-like URL evidence and may be applied after review.",
            evidence=evidence,
        )
    return RepairAssessment(
        repair_status="manual_review_required",
        decision="manual_review_required",
        normalized_repair_url=assessed.normalized_url,
        selected_source_type=assessed.source_type,
        reason=f"Repair candidate did not pass automatic URL-repair policy: {allowed_reason}.",
        evidence=evidence,
    )


def load_queue_item(conn: psycopg.Connection[Any], company_key: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                candidate_id,
                company_key,
                display_company_name,
                candidate_url,
                source_type_candidate,
                candidate_status,
                feasibility_review_id,
                queue_action,
                url_quality_status,
                url_quality_feedback_code,
                url_repair_candidate_url,
                queue_reason
            FROM gold_connector_build_candidate_queue
            WHERE company_key = %s
            ORDER BY queue_priority, last_signal_at DESC NULLS LAST
            LIMIT 1
            """,
            (company_key,),
        )
        return cur.fetchone()


def persist_repair_review(
    conn: psycopg.Connection[Any],
    *,
    queue_item: dict[str, Any],
    assessment: RepairAssessment,
    reviewed_by: str,
    write_applied: bool,
) -> int:
    repair_status = "repair_applied" if write_applied else assessment.repair_status
    applied_at_sql = "now()" if write_applied else "NULL"
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO employer_origin_url_repair_reviews (
                candidate_id,
                feasibility_review_id,
                company_key,
                company_name,
                previous_candidate_url,
                repair_candidate_url,
                normalized_repair_url,
                selected_source_type,
                repair_status,
                decision,
                reason,
                boundary,
                evidence,
                reviewed_by,
                applied_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s::jsonb, %s, {applied_at_sql}
            )
            RETURNING id
            """,
            (
                queue_item["candidate_id"],
                queue_item["feasibility_review_id"],
                queue_item["company_key"],
                queue_item["display_company_name"],
                queue_item["candidate_url"],
                queue_item["url_repair_candidate_url"],
                assessment.normalized_repair_url,
                assessment.selected_source_type,
                repair_status,
                assessment.decision,
                assessment.reason,
                json.dumps(BOUNDARY, sort_keys=True),
                json.dumps({
                    "queue_action": queue_item["queue_action"],
                    "url_quality_status": queue_item["url_quality_status"],
                    "url_quality_feedback_code": queue_item["url_quality_feedback_code"],
                    "queue_reason": queue_item["queue_reason"],
                    "assessment": assessment.evidence,
                }, sort_keys=True),
                reviewed_by,
            ),
        )
        review_id = int(cur.fetchone()["id"])
    return review_id


def apply_candidate_url_repair(
    conn: psycopg.Connection[Any],
    *,
    queue_item: dict[str, Any],
    assessment: RepairAssessment,
    reviewed_by: str,
) -> None:
    if assessment.decision != "apply_repair_candidate_url" or not assessment.normalized_repair_url:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE employer_origin_source_candidates
            SET candidate_url = %s::text,
                source_type_candidate = COALESCE(%s::text, source_type_candidate),
                notes = concat_ws(
                    ' ',
                    nullif(notes, ''),
                    %s::text
                ),
                updated_at = now()
            WHERE id = %s
            """,
            (
                assessment.normalized_repair_url,
                assessment.selected_source_type,
                f"Origin URL repaired from S7N/S7O feasibility feedback; reviewed_by={reviewed_by}.",
                queue_item["candidate_id"],
            ),
        )


def run(*, company_key: str, reviewed_by: str, write: bool, repair_url: str | None = None) -> dict[str, Any]:
    with connect() as conn:
        queue_item = load_queue_item(conn, company_key)
        if queue_item is None:
            raise ValueError(f"No S7O queue item found for company_key={company_key!r}.")
        repair_candidate_url = repair_url or queue_item.get("url_repair_candidate_url")
        if not repair_candidate_url:
            assessment = RepairAssessment(
                repair_status="not_applicable",
                decision="no_action",
                normalized_repair_url=None,
                selected_source_type=None,
                reason="No repair candidate URL is available for this queue item.",
                evidence={"queue_action": queue_item.get("queue_action")},
            )
        elif queue_item.get("queue_action") != "origin_url_repair_required" and repair_url is None:
            assessment = RepairAssessment(
                repair_status="not_applicable",
                decision="no_action",
                normalized_repair_url=None,
                selected_source_type=None,
                reason="Queue item is not classified as origin_url_repair_required.",
                evidence={"queue_action": queue_item.get("queue_action")},
            )
        else:
            assessment = assess_repair_candidate(
                company_key=str(queue_item["company_key"]),
                company_name=str(queue_item["display_company_name"]),
                repair_url=str(repair_candidate_url),
            )

        review_id = None
        write_applied = False
        if write:
            if assessment.decision == "apply_repair_candidate_url":
                apply_candidate_url_repair(conn, queue_item=queue_item, assessment=assessment, reviewed_by=reviewed_by)
                write_applied = True
            review_id = persist_repair_review(
                conn,
                queue_item=queue_item,
                assessment=assessment,
                reviewed_by=reviewed_by,
                write_applied=write_applied,
            )
            conn.commit()

    return {
        "company_key": queue_item["company_key"],
        "company_name": queue_item["display_company_name"],
        "queue_action": queue_item["queue_action"],
        "previous_candidate_url": queue_item["candidate_url"],
        "repair_candidate_url": repair_candidate_url,
        "repair_status": "repair_applied" if write_applied else assessment.repair_status,
        "decision": assessment.decision,
        "normalized_repair_url": assessment.normalized_repair_url,
        "selected_source_type": assessment.selected_source_type,
        "reason": assessment.reason,
        "write_requested": write,
        "persisted_review_id": review_id,
    }


def print_result(result: dict[str, Any]) -> None:
    print("S7P Reviewed Origin URL Repair Application")
    print("boundary: candidate URL repair only; no connector build, registration, activation, Bronze write or scheduler change")
    print("---")
    for key, value in result.items():
        print(f"{key}: {value if value is not None else '-'}")
    if result["decision"] == "apply_repair_candidate_url":
        print("next: rerun connector feasibility probe for the repaired company key")
    elif result["decision"] == "manual_review_required":
        print("next: inspect the repair URL manually before applying it")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply reviewed origin URL repairs from S7O queue.")
    parser.add_argument("--company-key", required=True)
    parser.add_argument("--reviewed-by", default="system")
    parser.add_argument("--repair-url", help="Override the S7O repair candidate URL after manual review.")
    parser.add_argument("--write", action="store_true", help="Persist the repair review and apply candidate_url when policy allows it.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = run(
        company_key=args.company_key,
        reviewed_by=args.reviewed_by,
        write=args.write,
        repair_url=args.repair_url,
    )
    print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
