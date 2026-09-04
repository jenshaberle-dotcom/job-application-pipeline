"""Read-only source/connector lifecycle overview with explicit truth boundaries."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol


SCHEMA_VERSION = "pipeline.source_connector_overview.v2"


class ConnectorRegistryLike(Protocol):
    exact_factories: Mapping[str, object]

    def create(self, source_name: str) -> object: ...

    def role_for(self, source_name: str) -> object: ...


def _get(row: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    return default if row is None else row.get(key, default)


def _count(row: Mapping[str, Any] | None, key: str) -> int:
    return int(_get(row, key, 0) or 0)


def _source_name(row: Mapping[str, Any]) -> str:
    return str(row.get("source_name") or row.get("source_name_candidate") or "").strip()


def _by_source(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    return {name: row for row in rows if (name := _source_name(row))}


def _latest_candidates(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    keys: dict[str, tuple[str, int]] = {}
    for row in rows:
        name = _source_name(row)
        if not name:
            continue
        key = (
            str(row.get("updated_at") or row.get("last_signal_at") or ""),
            int(row.get("candidate_id") or row.get("id") or 0),
        )
        if name not in keys or key >= keys[name]:
            result[name], keys[name] = row, key
    return result


def _source_role(registry: ConnectorRegistryLike, source_name: str) -> str:
    role_for = getattr(registry, "role_for", None)
    if role_for is None:
        return "unknown"
    try:
        role = role_for(source_name)
    except (KeyError, ValueError):
        return "unknown"
    except Exception:  # pragma: no cover - runtime diagnostic only
        return "unknown"
    value = getattr(role, "value", role)
    normalized = str(value or "unknown").strip().lower()
    return normalized or "unknown"


def _gate(
    candidate: Mapping[str, Any] | None,
    prefix: str,
    required_decision: str | None = None,
) -> dict[str, Any]:
    status = str(_get(candidate, f"{prefix}_status") or "unknown")
    raw_decision = _get(candidate, f"{prefix}_decision")
    decision = str(raw_decision) if raw_decision else None
    return {
        "status": status,
        "decision": decision,
        "passed": status == "passed"
        and (required_decision is None or decision == required_decision),
        "required": True,
        "truth_source": (
            "employer_origin_candidate_gate_reviews" if candidate else "unknown"
        ),
    }


def _not_applicable_gate() -> dict[str, Any]:
    return {
        "status": "not_applicable",
        "decision": None,
        "passed": True,
        "required": False,
        "truth_source": "connector_registry.source_role",
    }


def _registration(registry: ConnectorRegistryLike, source_name: str) -> dict[str, Any]:
    try:
        connector = registry.create(source_name)
    except ValueError as exc:
        return {
            "registered": False,
            "status": "not_registered",
            "connector_class": None,
            "error": None,
            "detail": str(exc),
        }
    except Exception as exc:  # pragma: no cover - runtime diagnostic only
        return {
            "registered": False,
            "status": "registration_error",
            "connector_class": None,
            "error": type(exc).__name__,
            "detail": str(exc),
        }
    connector_type = type(connector)
    return {
        "registered": True,
        "status": "registered",
        "connector_class": f"{connector_type.__module__}.{connector_type.__name__}",
        "error": None,
        "detail": None,
    }


def _profile_status(profile: Mapping[str, Any] | None, available: bool) -> str:
    if not available:
        return "unknown"
    total, active = _count(profile, "profile_count"), _count(profile, "active_profile_count")
    if total == 0:
        return "not_configured"
    if active == 0:
        return "inactive"
    return "active" if active == total else "mixed"


def _layer_status(
    bronze: int,
    silver: int,
    ingestion_observed: bool,
    bronze_available: bool,
    silver_available: bool,
) -> str:
    if not bronze_available and not silver_available:
        return "unknown"
    if not bronze_available or not silver_available:
        return "partial_truth"
    if silver and not bronze:
        return "inconsistent_silver_without_bronze"
    if bronze and silver:
        return "bronze_and_silver_present"
    if bronze:
        return "bronze_only"
    return "ingestion_run_without_persisted_rows" if ingestion_observed else "no_ingestion"


def _run_health(
    run: Mapping[str, Any] | None,
    *,
    available: bool,
) -> dict[str, Any]:
    if not available:
        return {
            "status": "unknown",
            "latest_run_status": "unknown",
            "truth_source": "ingestion_runs",
            "truth_available": False,
        }
    raw = str(_get(run, "last_ingestion_status") or "not_run").strip().lower()
    status = {
        "success": "healthy",
        "failed": "failed",
        "running": "running",
        "not_run": "not_run",
    }.get(raw, "unknown")
    return {
        "status": status,
        "latest_run_status": raw,
        "truth_source": "ingestion_runs",
        "truth_available": True,
    }


def _lifecycle(
    implemented: bool,
    validation: Mapping[str, Any],
    approval: Mapping[str, Any],
    registered: bool,
    activated: bool | None,
    ingested: bool | None,
) -> dict[str, str]:
    validation_status = (
        "not_applicable"
        if not validation.get("required", True)
        else ("passed" if validation["passed"] else str(validation["status"]))
    )
    approval_status = (
        "not_applicable"
        if not approval.get("required", True)
        else ("approved" if approval["passed"] else str(approval["status"]))
    )
    return {
        "implementation": "implemented" if implemented else "not_implemented",
        "validation": validation_status,
        "final_approval": approval_status,
        "registration": "registered" if registered else "not_registered",
        "activation": (
            "unknown" if activated is None else ("active" if activated else "not_activated")
        ),
        "ingestion": (
            "unknown" if ingested is None else ("ingested" if ingested else "not_ingested")
        ),
    }


def _issues(
    candidate_status: str,
    validation: Mapping[str, Any],
    approval: Mapping[str, Any],
    registered: bool,
    registration_status: str,
    activated: bool | None,
    bronze: int,
    silver: int,
    bronze_available: bool,
    silver_available: bool,
    *,
    source_role: str,
    run_health: Mapping[str, Any],
) -> list[str]:
    issues: list[str] = []
    origin_gates_required = source_role != "sensor"
    if registration_status == "registration_error":
        issues.append("connector_registry_factory_error")
    if activated and not registered:
        issues.append("active_source_without_code_backed_registration")
    if origin_gates_required and activated and not validation["passed"]:
        issues.append("active_source_without_proven_validation_gate")
    if origin_gates_required and activated and not approval["passed"]:
        issues.append("active_source_without_proven_final_approval")
    if candidate_status == "active_controlled" and activated is False:
        issues.append("candidate_marked_active_without_active_search_profile")
    if (bronze or silver) and activated is False:
        issues.append("persisted_ingestion_data_without_active_search_profile")
    if bronze_available and silver_available and silver and not bronze:
        issues.append("silver_rows_without_bronze_rows")
    if source_role == "sensor" and activated is True:
        if run_health["status"] == "failed":
            issues.append("market_sensor_latest_run_failed")
        elif run_health["status"] == "unknown":
            issues.append("market_sensor_run_health_unknown")
        elif run_health["status"] == "not_run" and (bronze or silver):
            issues.append("market_sensor_run_evidence_missing")
    return issues


def _next_action(
    implemented: bool,
    validation: Mapping[str, Any],
    approval: Mapping[str, Any],
    registered: bool,
    activated: bool | None,
    ingested: bool | None,
    bronze: int,
    silver: int,
    issues: Sequence[str],
    *,
    source_role: str,
) -> tuple[str | None, str]:
    if issues:
        issue_actions = {
            "market_sensor_latest_run_failed": "Run a bounded live sensor probe and resolve the latest ingestion failure",
            "market_sensor_run_health_unknown": "Inspect the latest sensor run status before trusting market coverage",
            "market_sensor_run_evidence_missing": "Restore sensor run evidence before trusting historical layer rows",
        }
        return issues[0], issue_actions.get(
            issues[0], "Resolve lifecycle truth inconsistency"
        )
    origin_gates_required = source_role != "sensor"
    stages = (
        (not implemented, "connector_not_implemented", "Implement the connector"),
        (
            origin_gates_required and not validation["passed"],
            "connector_validation_incomplete",
            "Complete the connector validation gate",
        ),
        (
            origin_gates_required and not approval["passed"],
            "final_approval_incomplete",
            "Complete the final approval gate",
        ),
        (not registered, "connector_not_registered", "Register the connector in code"),
        (
            activated is None,
            "activation_truth_unavailable",
            "Restore the search-profile truth source before lifecycle decisions",
        ),
        (
            activated is False,
            "controlled_activation_not_completed",
            "Review controlled activation as a separate bounded slice",
        ),
        (
            ingested is None,
            "ingestion_truth_unavailable",
            "Restore Bronze and Silver truth sources before ingestion decisions",
        ),
        (
            bronze == 0 and silver == 0,
            "no_persisted_ingestion",
            "Run separately approved bounded ingestion",
        ),
        (
            bronze > 0 and silver == 0,
            "silver_processing_pending",
            "Validate and process Bronze rows to Silver",
        ),
    )
    for applies, blocker, action in stages:
        if applies:
            return blocker, action
    return None, (
        "Monitor market-sensor run health and ingestion quality"
        if source_role == "sensor"
        else "Monitor source lifecycle and ingestion quality"
    )


def empty_source_connector_overview() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "source_count": 0,
            "sensor_count": 0,
            "healthy_sensor_count": 0,
            "employer_origin_count": 0,
            "implemented_count": 0,
            "validated_count": 0,
            "final_approved_count": 0,
            "registered_count": 0,
            "active_count": 0,
            "ingested_count": 0,
            "attention_count": 0,
        },
        "sources": [],
        "boundaries": {
            "read_only": True,
            "no_source_activation": True,
            "no_ingestion": True,
            "no_scheduler_mutation": True,
            "unknown_is_not_success": True,
            "registration_is_not_activation": True,
            "sensor_gates_are_role_specific": True,
            "historical_layers_are_not_live_sensor_health": True,
        },
    }


def build_source_connector_overview(
    *,
    registry: ConnectorRegistryLike,
    candidates: Sequence[Mapping[str, Any]] = (),
    search_profiles: Sequence[Mapping[str, Any]] = (),
    ingestion_runs: Sequence[Mapping[str, Any]] = (),
    layer_presence: Sequence[Mapping[str, Any]] = (),
    implementation_probe: Callable[[Mapping[str, Any]], bool] | None = None,
    truth_availability: Mapping[str, bool] | None = None,
) -> dict[str, Any]:
    """Assemble deterministic lifecycle truth without mutating any input."""

    availability = {
        "search_profiles": True,
        "ingestion_runs": True,
        "raw_jobs": True,
        "silver_jobs": True,
        **(truth_availability or {}),
    }
    candidates_by_source = _latest_candidates(candidates)
    profiles_by_source = _by_source(search_profiles)
    runs_by_source = _by_source(ingestion_runs)
    layers_by_source = _by_source(layer_presence)
    source_names = set(getattr(registry, "exact_factories", {}).keys())
    for rows in (candidates_by_source, profiles_by_source, runs_by_source, layers_by_source):
        source_names.update(rows)

    sources: list[dict[str, Any]] = []
    for source_name in sorted(source_names):
        candidate = candidates_by_source.get(source_name)
        profile = profiles_by_source.get(source_name)
        run = runs_by_source.get(source_name)
        layers = layers_by_source.get(source_name)
        source_role = _source_role(registry, source_name)
        registration = _registration(registry, source_name)
        probed = (
            implementation_probe(candidate)
            if implementation_probe and candidate is not None
            else bool(_get(candidate, "connector_implemented", False))
        )
        implemented = bool(registration["registered"] or probed)
        if source_role == "sensor":
            validation = _not_applicable_gate()
            approval = _not_applicable_gate()
        else:
            validation = _gate(candidate, "connector_validation_gate")
            approval = _gate(
                candidate,
                "final_approval_gate",
                "approve_connector_registration",
            )
        profile_count = _count(profile, "profile_count")
        active_count = _count(profile, "active_profile_count")
        activated = active_count > 0 if availability["search_profiles"] else None
        bronze, silver = _count(layers, "bronze_count"), _count(layers, "silver_count")
        observed_rows = (availability["raw_jobs"] and bronze > 0) or (
            availability["silver_jobs"] and silver > 0
        )
        ingested = (
            True
            if observed_rows
            else (
                False
                if availability["raw_jobs"] and availability["silver_jobs"]
                else None
            )
        )
        run_health = _run_health(run, available=availability["ingestion_runs"])
        candidate_status = str(_get(candidate, "candidate_status") or "unknown")
        candidate_id = int(
            _get(candidate, "candidate_id") or _get(candidate, "id") or 0
        ) or None
        issues = _issues(
            candidate_status,
            validation,
            approval,
            bool(registration["registered"]),
            str(registration["status"]),
            activated,
            bronze,
            silver,
            availability["raw_jobs"],
            availability["silver_jobs"],
            source_role=source_role,
            run_health=run_health,
        )
        blocker, next_action = _next_action(
            implemented,
            validation,
            approval,
            bool(registration["registered"]),
            activated,
            ingested,
            bronze,
            silver,
            issues,
            source_role=source_role,
        )
        company_name = str(_get(candidate, "company_name") or "").strip()
        source_type = str(_get(candidate, "source_type") or "").strip() or (
            "market_sensor" if source_role == "sensor" else "unknown"
        )
        sources.append(
            {
                "candidate_id": candidate_id,
                "source_name": source_name,
                "source_label": company_name
                or source_name.replace(":", " · ").replace("_", " ").title(),
                "source_type": source_type,
                "source_role": source_role,
                "candidate_status": candidate_status,
                "connector": {
                    "implemented": implemented,
                    "implementation_status": (
                        "implemented" if implemented else "not_implemented"
                    ),
                    "implementation_truth_source": (
                        "runtime_registry"
                        if registration["registered"]
                        else ("connector_module_path" if probed else "unknown")
                    ),
                    "code_backed_registered": bool(registration["registered"]),
                    "registration_status": registration["status"],
                    "connector_class": registration["connector_class"],
                    "registration_error": registration["error"],
                },
                "gates": {
                    "connector_validation_gate": validation,
                    "final_approval_gate": approval,
                },
                "activation": {
                    "status": (
                        "unknown"
                        if activated is None
                        else ("active" if activated else "not_activated")
                    ),
                    "active": activated,
                    "truth_source": "search_profiles.is_active",
                    "truth_available": availability["search_profiles"],
                },
                "search_profiles": {
                    "status": _profile_status(profile, availability["search_profiles"]),
                    "profile_count": profile_count,
                    "active_profile_count": active_count,
                    "active_search_term_count": _count(profile, "active_search_term_count"),
                    "truth_source": "search_profiles/search_terms",
                    "truth_available": availability["search_profiles"],
                },
                "operational_health": {
                    **run_health,
                    "applies": source_role == "sensor",
                },
                "last_ingestion": {
                    "status": (
                        str(_get(run, "last_ingestion_status") or "not_run")
                        if availability["ingestion_runs"]
                        else "unknown"
                    ),
                    "started_at": _get(run, "started_at"),
                    "finished_at": _get(run, "finished_at"),
                    "total_loaded": _count(run, "total_loaded"),
                    "inserted_count": _count(run, "inserted_count"),
                    "error_message": _get(run, "error_message"),
                    "truth_source": "ingestion_runs",
                    "truth_available": availability["ingestion_runs"],
                },
                "layers": {
                    "status": _layer_status(
                        bronze,
                        silver,
                        run is not None,
                        availability["raw_jobs"],
                        availability["silver_jobs"],
                    ),
                    "bronze_present": bronze > 0 if availability["raw_jobs"] else None,
                    "bronze_count": bronze,
                    "silver_present": silver > 0 if availability["silver_jobs"] else None,
                    "silver_count": silver,
                    "truth_source": "raw_jobs/silver_jobs",
                    "bronze_truth_available": availability["raw_jobs"],
                    "silver_truth_available": availability["silver_jobs"],
                },
                "lifecycle": _lifecycle(
                    implemented,
                    validation,
                    approval,
                    bool(registration["registered"]),
                    activated,
                    ingested,
                ),
                "inconsistencies": issues,
                "current_blocker": blocker,
                "next_action": next_action,
            }
        )

    def count_where(predicate: Callable[[Mapping[str, Any]], bool]) -> int:
        return sum(1 for source in sources if predicate(source))

    payload = empty_source_connector_overview()
    payload["summary"] = {
        "source_count": len(sources),
        "sensor_count": count_where(lambda s: s["source_role"] == "sensor"),
        "healthy_sensor_count": count_where(
            lambda s: s["source_role"] == "sensor"
            and s["activation"]["active"] is True
            and s["operational_health"]["status"] == "healthy"
            and s["current_blocker"] is None
        ),
        "employer_origin_count": count_where(
            lambda s: s["source_role"] == "employer_origin"
        ),
        "implemented_count": count_where(lambda s: bool(s["connector"]["implemented"])),
        "validated_count": count_where(
            lambda s: bool(s["gates"]["connector_validation_gate"]["required"])
            and bool(s["gates"]["connector_validation_gate"]["passed"])
        ),
        "final_approved_count": count_where(
            lambda s: bool(s["gates"]["final_approval_gate"]["required"])
            and bool(s["gates"]["final_approval_gate"]["passed"])
        ),
        "registered_count": count_where(
            lambda s: bool(s["connector"]["code_backed_registered"])
        ),
        "active_count": count_where(lambda s: s["activation"]["active"] is True),
        "ingested_count": count_where(
            lambda s: s["layers"]["bronze_present"] is True
            or s["layers"]["silver_present"] is True
        ),
        "attention_count": count_where(lambda s: s["current_blocker"] is not None),
    }
    payload["sources"] = sources
    return payload
