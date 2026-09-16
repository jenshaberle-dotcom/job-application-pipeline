"""Read-only F4C source-health/operator-surface reconciliation.

This diagnostic measures the Product source-health projection and the frontend
ownership boundaries.  It preserves the original historical-success diagnostic
while also proving the consolidated F4C operator surface: Sources owns source
health, the redundant Operations navigation is hidden, and Data Layers owns layer
flow without a competing per-source last-run table.
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig

ROOT = Path(__file__).resolve().parents[1]


class ReconciliationStop(RuntimeError):
    """Fail closed when the Product payload cannot support the diagnostic."""


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        current = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        try:
            current = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _age_hours(value: object, *, observed_at: datetime) -> float | None:
    normalized = _iso(value)
    if normalized is None:
        return None
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    delta = observed_at - parsed.astimezone(timezone.utc)
    return round(max(0.0, delta.total_seconds() / 3600.0), 2)


def load_recurring_profile_evidence() -> dict[str, dict[str, object]]:
    """Read scheduling eligibility only; eligibility is deliberately not cadence."""

    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.search_profiles') IS NOT NULL AS present")
            relation = cur.fetchone()
            if not relation or not relation["present"]:
                return {}
            cur.execute(
                """
                SELECT
                    source_name,
                    count(*)::integer AS profile_count,
                    count(*) FILTER (WHERE is_active)::integer AS active_profile_count,
                    count(*) FILTER (
                        WHERE is_active AND recurring_ingestion_enabled
                    )::integer AS recurring_enabled_profile_count
                FROM search_profiles
                GROUP BY source_name
                ORDER BY source_name
                """
            )
            return {
                str(row["source_name"]): {
                    "profile_count": int(row["profile_count"] or 0),
                    "active_profile_count": int(row["active_profile_count"] or 0),
                    "recurring_enabled_profile_count": int(
                        row["recurring_enabled_profile_count"] or 0
                    ),
                }
                for row in cur.fetchall()
            }


def surface_contract_evidence() -> dict[str, object]:
    """Measure current semantic ownership from the active frontend sources."""

    workspace = (ROOT / "frontend/control-center/src/OperatorWorkspace.tsx").read_text(
        encoding="utf-8"
    )
    layers = (ROOT / "frontend/control-center/src/DataLayersTab.tsx").read_text(
        encoding="utf-8"
    )
    source_health = (
        ROOT / "frontend/control-center/src/F4cSourceHealthSurface.tsx"
    ).read_text(encoding="utf-8")
    main = (ROOT / "frontend/control-center/src/main.tsx").read_text(encoding="utf-8")
    return {
        "active_workspace": "import App from \"./OperatorWorkspace\"" in main,
        "sources_owns_source_connector_overview": (
            "function Sources" in workspace and "source_connector_overview" in workspace
        ),
        # The legacy component still exists in OperatorWorkspace, but F4C removes
        # it from the top-level operator navigation until a distinct runtime model exists.
        "operations_reuses_source_lifecycle_summary": (
            "function Operations" in workspace
            and "const overview = payload.source_connector_overview.summary" in workspace
            and "<h2>Source lifecycle</h2>" in workspace
        ),
        "operations_top_level_hidden": (
            '.includes("Operations")' in source_health
            and 'wrapper.dataset.f4cHidden = "true"' in source_health
        ),
        "data_layers_has_per_source_last_run_projection": (
            "type SourceRow" in layers
            and "last_run_status" in layers
            and "<h2>Source contribution</h2>" in layers
        ),
        "data_layers_owns_bronze_silver_gold_flow": (
            "Layer flow" in layers
            and "Bronze new" in layers
            and "Silver normalized" in layers
            and "Gold assessed" in layers
        ),
        "data_layers_separates_persisted_and_current_scope": (
            "Persisted inventory" in layers and "Current Product scope" in layers
        ),
    }


def reconcile(
    payload: Mapping[str, object],
    *,
    recurring_profiles: Mapping[str, Mapping[str, object]],
    source_sha: str,
    observed_at: datetime,
    surface_evidence: Mapping[str, object],
) -> dict[str, object]:
    overview = payload.get("source_connector_overview")
    if not isinstance(overview, Mapping):
        raise ReconciliationStop("SOURCE_CONNECTOR_OVERVIEW_MISSING")
    raw_sources = overview.get("sources")
    if not isinstance(raw_sources, Sequence) or isinstance(raw_sources, (str, bytes)):
        raise ReconciliationStop("SOURCE_CONNECTOR_ROWS_INVALID")
    if not raw_sources:
        raise ReconciliationStop("SOURCE_CONNECTOR_ROWS_EMPTY")

    rows: list[dict[str, object]] = []
    for raw in raw_sources:
        if not isinstance(raw, Mapping):
            raise ReconciliationStop("SOURCE_CONNECTOR_ROW_INVALID")
        source_name = str(raw.get("source_name") or "").strip()
        if not source_name:
            raise ReconciliationStop("SOURCE_NAME_MISSING")
        activation = _as_mapping(raw.get("activation"))
        operational = _as_mapping(raw.get("operational_health"))
        ingestion = _as_mapping(raw.get("last_ingestion"))
        layers = _as_mapping(raw.get("layers"))
        profile = recurring_profiles.get(source_name, {})

        latest_run_status = str(
            operational.get("latest_run_status")
            or ingestion.get("status")
            or "unknown"
        ).strip().lower()
        operational_health = str(operational.get("status") or "unknown").strip().lower()
        last_run_at = ingestion.get("finished_at") or ingestion.get("started_at")
        recurring_count = int(profile.get("recurring_enabled_profile_count") or 0)
        active_profile_count = int(
            profile.get("active_profile_count")
            or _as_mapping(raw.get("search_profiles")).get("active_profile_count")
            or 0
        )
        active = activation.get("active") is True
        healthy_from_latest_success = (
            operational_health == "healthy" and latest_run_status == "success"
        )

        # This legacy reconciliation intentionally records whether the input Product
        # projection made a current-health claim without cadence authority.  The F4C
        # current-health proof separately verifies that the live projection no longer does.
        cadence_authority = "not_projected"
        current_health_support = (
            "historical_run_success_only_no_cadence_freshness_authority"
            if healthy_from_latest_success
            else "no_current_healthy_claim"
        )

        loaded = int(ingestion.get("total_loaded") or 0)
        inserted = int(ingestion.get("inserted_count") or 0)
        bronze = int(layers.get("bronze_count") or 0)
        silver = int(layers.get("silver_count") or 0)
        rows.append(
            {
                "source_name": source_name,
                "source_label": str(raw.get("source_label") or source_name),
                "source_role": str(raw.get("source_role") or "unknown"),
                "candidate_status": str(raw.get("candidate_status") or "unknown"),
                "activation_active": activation.get("active"),
                "activation_status": str(activation.get("status") or "unknown"),
                "active_profile_count": active_profile_count,
                "recurring_enabled_profile_count": recurring_count,
                "recurring_ingestion_eligible": recurring_count > 0,
                "explicit_cadence_authority": cadence_authority,
                "latest_run_status": latest_run_status,
                "last_run_at": _iso(last_run_at),
                "last_run_age_hours": _age_hours(last_run_at, observed_at=observed_at),
                "product_operational_health": operational_health,
                "healthy_from_latest_success": healthy_from_latest_success,
                "current_health_claim_support": current_health_support,
                "current_reachability": "unknown_not_measured_by_source_overview",
                "delivery": {
                    "last_loaded": loaded,
                    "last_inserted": inserted,
                    "bronze_count": bronze,
                    "silver_count": silver,
                    "active_zero_last_run_delivery": (
                        active and latest_run_status == "success" and loaded == 0
                    ),
                },
                "current_blocker": raw.get("current_blocker"),
                "next_action": str(raw.get("next_action") or ""),
            }
        )

    health_counts = Counter(str(row["product_operational_health"]) for row in rows)
    latest_counts = Counter(str(row["latest_run_status"]) for row in rows)
    healthy_without_cadence = sum(
        row["product_operational_health"] == "healthy"
        and row["explicit_cadence_authority"] == "not_projected"
        for row in rows
    )
    return {
        "schema": "jap.f4c.source_health_reconciliation.v1",
        "source_sha": source_sha,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(),
        "authority": "diagnostic_only_no_health_policy_mutation",
        "summary": {
            "source_count": len(rows),
            "product_operational_health": dict(sorted(health_counts.items())),
            "latest_run_status": dict(sorted(latest_counts.items())),
            "latest_success_rendered_healthy_count": sum(
                bool(row["healthy_from_latest_success"]) for row in rows
            ),
            "healthy_without_explicit_cadence_freshness_authority_count": (
                healthy_without_cadence
            ),
            "recurring_ingestion_eligible_source_count": sum(
                bool(row["recurring_ingestion_eligible"]) for row in rows
            ),
            "active_zero_last_run_delivery_count": sum(
                bool(_as_mapping(row["delivery"])["active_zero_last_run_delivery"])
                for row in rows
            ),
            "current_reachability_measured_count": 0,
            "operations_source_lifecycle_overlap": bool(
                surface_evidence.get("operations_reuses_source_lifecycle_summary")
            ),
            "operations_top_level_hidden": bool(
                surface_evidence.get("operations_top_level_hidden")
            ),
            "data_layers_per_source_run_overlap": bool(
                surface_evidence.get("data_layers_has_per_source_last_run_projection")
            ),
            "data_layers_scope_separated": bool(
                surface_evidence.get("data_layers_separates_persisted_and_current_scope")
            ),
        },
        "surface_contract_evidence": dict(surface_evidence),
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
            "recurring_eligibility_is_not_cadence": True,
            "run_success_is_not_current_reachability": True,
            "zero_delivery_is_not_source_failure": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    observed_at = datetime.now(timezone.utc)
    payload = __import__(
        "scripts.product_v1_control_center_base", fromlist=["load_product_v1_payload"]
    ).load_product_v1_payload(include_source_connector_overview=True)
    report = reconcile(
        payload,
        recurring_profiles=load_recurring_profile_evidence(),
        source_sha=args.source_sha,
        observed_at=observed_at,
        surface_evidence=surface_contract_evidence(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
