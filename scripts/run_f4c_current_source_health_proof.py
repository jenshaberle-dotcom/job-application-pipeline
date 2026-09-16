"""Real read-only F4C Product proof for source operator semantics."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from scripts.product_v1_control_center_base import load_product_v1_payload
from scripts.product_v1_f4c_source_health_runtime import (
    load_source_operator_evidence,
    load_source_schedule_evidence,
    project_current_source_health,
)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def build_report(*, source_sha: str, observed_at: datetime | None = None) -> dict[str, object]:
    now = observed_at or datetime.now(timezone.utc)
    raw = load_product_v1_payload()
    schedules = load_source_schedule_evidence()
    operator_evidence = load_source_operator_evidence()
    projected = project_current_source_health(
        raw,
        schedule_evidence=schedules,
        operator_evidence=operator_evidence,
        observed_at=now,
    )

    raw_overview = _mapping(raw.get("source_connector_overview"))
    projected_overview = _mapping(projected.get("source_connector_overview"))
    raw_sources = raw_overview.get("sources")
    projected_sources = projected_overview.get("sources")
    if not isinstance(raw_sources, list) or not isinstance(projected_sources, list):
        raise RuntimeError("F4C_SOURCE_OVERVIEW_MISSING")
    if len(raw_sources) != len(projected_sources):
        raise RuntimeError("F4C_SOURCE_COHORT_CHANGED_BY_PROJECTION")

    prior_by_name = {
        str(row.get("source_name") or ""): row
        for row in raw_sources
        if isinstance(row, Mapping)
    }
    rows: list[dict[str, object]] = []
    current_health_counts: Counter[str] = Counter()
    scan_counts: Counter[str] = Counter()
    historical_success_healthy = 0
    success_without_cadence_unknown = 0
    zero_yield_success = 0
    reachability_not_checked = 0
    comparable_disappearance = 0

    for projected_row in projected_sources:
        if not isinstance(projected_row, Mapping):
            continue
        source_name = str(projected_row.get("source_name") or "")
        prior_row = _mapping(prior_by_name.get(source_name))
        prior_health = _mapping(prior_row.get("operational_health"))
        current_health = _mapping(projected_row.get("operational_health"))
        scan = _mapping(projected_row.get("source_scan"))
        scheduling = _mapping(projected_row.get("scheduling"))
        reachability = _mapping(projected_row.get("reachability"))
        delivery = _mapping(projected_row.get("delivery"))
        activation = _mapping(projected_row.get("activation"))

        latest = str(current_health.get("latest_run_status") or "unknown")
        prior_status = str(prior_health.get("status") or "unknown")
        current_status = str(current_health.get("status") or "unknown")
        current_health_counts[current_status] += 1
        scan_counts[str(scan.get("status") or "unknown")] += 1

        if latest == "success" and prior_status == "healthy":
            historical_success_healthy += 1
        if (
            latest == "success"
            and current_status == "unknown"
            and current_health.get("reason")
            == "successful_run_without_explicit_cadence_authority"
        ):
            success_without_cadence_unknown += 1
        if delivery.get("latest_success_zero_yield") is True:
            zero_yield_success += 1
        if reachability.get("status") == "not_checked":
            reachability_not_checked += 1
        if delivery.get("disappeared_comparison_available") is True:
            comparable_disappearance += 1

        rows.append(
            {
                "source_name": source_name,
                "source_role": projected_row.get("source_role"),
                "active": activation.get("active"),
                "latest_run_status": latest,
                "latest_scan_status": scan.get("status"),
                "latest_scan_at": scan.get("finished_at"),
                "historical_product_health": prior_status,
                "internal_current_health": current_status,
                "internal_current_health_reason": current_health.get("reason"),
                "recurring_ingestion_eligible": scheduling.get(
                    "recurring_ingestion_eligible"
                ),
                "live_reachability": reachability.get("status"),
                "current_job_count": delivery.get("current_job_count"),
                "last_job_delivery_at": delivery.get("last_job_delivery_at"),
                "latest_job_observed_at": delivery.get("latest_job_observed_at"),
                "source_data_age_hours": delivery.get("source_data_age_hours"),
                "disappeared_comparison_available": delivery.get(
                    "disappeared_comparison_available"
                ),
                "disappeared_since_previous_success": delivery.get(
                    "disappeared_since_previous_success"
                ),
                "zero_yield_latest_success": delivery.get(
                    "latest_success_zero_yield"
                ),
                "current_blocker": projected_row.get("current_blocker"),
            }
        )

    summary = {
        "source_count": len(rows),
        "historical_success_rendered_healthy_count": historical_success_healthy,
        "success_without_cadence_projected_unknown_count": success_without_cadence_unknown,
        "zero_yield_latest_success_count": zero_yield_success,
        "reachability_not_checked_count": reachability_not_checked,
        "disappeared_comparable_source_count": comparable_disappearance,
        "internal_current_health": dict(sorted(current_health_counts.items())),
        "latest_scan_status": dict(sorted(scan_counts.items())),
        "schedule_evidence_source_count": len(schedules),
        "operator_evidence_source_count": len(operator_evidence),
    }
    return {
        "schema_version": "f4c.source_operator_evidence_proof.v2",
        "source_sha": source_sha,
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "summary": summary,
        "rows": rows,
        "boundaries": {
            "db_writes": 0,
            "provider_calls": 0,
            "network_probes": 0,
            "source_activation_changed": False,
            "scheduler_changed": False,
            "ranking_authority_changed": False,
            "top5_authority_changed": False,
            "application_authority_changed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = build_report(source_sha=args.source_sha)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
