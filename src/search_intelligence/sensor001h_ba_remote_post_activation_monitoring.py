from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from src.search_intelligence.market_sensor_controlled_activation import (
    BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
    BA_SOURCE_NAME,
    EXPECTED_BA_REMOTE_TERMS,
    MarketSensorProfileState,
    MarketSensorTermState,
)

ACTIVATION_OK_STATUSES = {"activation_applied", "already_active_controlled_profile"}


@dataclass(frozen=True)
class Sensor001HActivationState:
    profile_id: int | None
    profile_name: str
    source_name: str
    current_is_active: bool
    page_size: int | None
    active_terms: tuple[str, ...]
    missing_expected_terms: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Sensor001HTermObservation:
    search_term: str
    ingestion_run_count: int
    raw_jobs_count: int
    total_loaded: int
    inserted_count: int
    duplicate_count: int
    failed_run_count: int
    latest_started_at: str | None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "Sensor001HTermObservation":
        return cls(
            search_term=str(row.get("search_term") or "<missing>"),
            ingestion_run_count=_to_int(row.get("ingestion_run_count")),
            raw_jobs_count=_to_int(row.get("raw_jobs_count")),
            total_loaded=_to_int(row.get("total_loaded")),
            inserted_count=_to_int(row.get("inserted_count")),
            duplicate_count=_to_int(row.get("duplicate_count")),
            failed_run_count=_to_int(row.get("failed_run_count")),
            latest_started_at=_optional_text(row.get("latest_started_at")),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Sensor001HLatestRun:
    run_id: int
    status: str
    search_term: str | None
    total_loaded: int
    inserted_count: int
    duplicate_count: int
    error_type: str | None
    error_stage: str | None
    error_message: str | None
    started_at: str | None
    finished_at: str | None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "Sensor001HLatestRun":
        return cls(
            run_id=_to_int(row.get("id")),
            status=str(row.get("status") or "unknown"),
            search_term=_optional_text(row.get("search_term")),
            total_loaded=_to_int(row.get("total_loaded")),
            inserted_count=_to_int(row.get("inserted_count")),
            duplicate_count=_to_int(row.get("duplicate_count")),
            error_type=_optional_text(row.get("error_type")),
            error_stage=_optional_text(row.get("error_stage")),
            error_message=_optional_text(row.get("error_message")),
            started_at=_optional_text(row.get("started_at")),
            finished_at=_optional_text(row.get("finished_at")),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Sensor001HMonitoringReport:
    overall_status: str
    source_status: str
    activation_state: Sensor001HActivationState
    term_observations: tuple[Sensor001HTermObservation, ...]
    latest_runs: tuple[Sensor001HLatestRun, ...]
    metric_summary: Mapping[str, Any]
    findings: tuple[str, ...]
    next_action: str
    safety_boundary: Mapping[str, bool]
    monitoring_contract: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "sensor001h.ba_remote_post_activation_monitoring.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "work_item": "SENSOR-001H BA Remote/Nationwide Post-Activation Monitoring",
            "source_name": BA_SOURCE_NAME,
            "review_profile_name": BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            "overall_status": self.overall_status,
            "source_status": self.source_status,
            "activation_state": self.activation_state.as_dict(),
            "term_observations": [observation.as_dict() for observation in self.term_observations],
            "latest_runs": [run.as_dict() for run in self.latest_runs],
            "metric_summary": dict(self.metric_summary),
            "findings": list(self.findings),
            "next_action": self.next_action,
            "safety_boundary": dict(self.safety_boundary),
            "monitoring_contract": dict(self.monitoring_contract),
        }


def build_sensor001h_post_activation_monitoring(
    *,
    sensor001g_report: Mapping[str, Any],
    profiles: Iterable[MarketSensorProfileState],
    terms: Iterable[MarketSensorTermState],
    term_observation_rows: Iterable[Mapping[str, Any]],
    latest_run_rows: Iterable[Mapping[str, Any]],
) -> Sensor001HMonitoringReport:
    source_status = str(sensor001g_report.get("overall_status") or "unknown")
    profile_tuple = tuple(profiles)
    term_tuple = tuple(terms)
    activation_state = _build_activation_state(profile_tuple, term_tuple)
    term_observations = tuple(Sensor001HTermObservation.from_mapping(row) for row in term_observation_rows)
    latest_runs = tuple(Sensor001HLatestRun.from_mapping(row) for row in latest_run_rows)
    metric_summary = _summarize(term_observations, latest_runs)
    safety_boundary = _safety_boundary()
    monitoring_contract = _monitoring_contract()

    if source_status not in ACTIVATION_OK_STATUSES:
        return Sensor001HMonitoringReport(
            overall_status="monitoring_blocked_until_activation_confirmed",
            source_status=source_status,
            activation_state=activation_state,
            term_observations=term_observations,
            latest_runs=latest_runs,
            metric_summary=metric_summary,
            findings=("SENSOR-001G has not confirmed an applied or already-active controlled profile state.",),
            next_action="Run or inspect SENSOR-001G before treating the profile as activated.",
            safety_boundary=safety_boundary,
            monitoring_contract=monitoring_contract,
        )

    if not activation_state.current_is_active:
        return Sensor001HMonitoringReport(
            overall_status="monitoring_blocked_profile_not_active",
            source_status=source_status,
            activation_state=activation_state,
            term_observations=term_observations,
            latest_runs=latest_runs,
            metric_summary=metric_summary,
            findings=("The BA remote/nationwide review profile is not active in the current database state.",),
            next_action="Do not monitor ingestion impact until SENSOR-001G activation is visible in the database.",
            safety_boundary=safety_boundary,
            monitoring_contract=monitoring_contract,
        )

    if activation_state.missing_expected_terms:
        return Sensor001HMonitoringReport(
            overall_status="monitoring_attention_required_configuration_gap",
            source_status=source_status,
            activation_state=activation_state,
            term_observations=term_observations,
            latest_runs=latest_runs,
            metric_summary=metric_summary,
            findings=("The active BA remote/nationwide profile is missing expected active search terms.",),
            next_action="Repair the profile terms before interpreting post-activation ingestion quality.",
            safety_boundary=safety_boundary,
            monitoring_contract=monitoring_contract,
        )

    if metric_summary["failed_run_count"] > 0:
        return Sensor001HMonitoringReport(
            overall_status="monitoring_attention_required_failed_runs",
            source_status=source_status,
            activation_state=activation_state,
            term_observations=term_observations,
            latest_runs=latest_runs,
            metric_summary=metric_summary,
            findings=("At least one post-activation run for the profile failed; inspect errors before promotion decisions.",),
            next_action="Inspect failed ingestion runs and repair before broadening or judging source quality.",
            safety_boundary=safety_boundary,
            monitoring_contract=monitoring_contract,
        )

    if metric_summary["ingestion_run_count"] == 0:
        return Sensor001HMonitoringReport(
            overall_status="monitoring_ready_awaiting_first_run",
            source_status=source_status,
            activation_state=activation_state,
            term_observations=term_observations,
            latest_runs=latest_runs,
            metric_summary=metric_summary,
            findings=(
                "The controlled BA remote/nationwide profile is active and ready for monitoring.",
                "No ingestion run for this profile is visible yet; this report is a baseline before impact measurement.",
            ),
            next_action="Wait for the next normal bounded run or request a separately approved ingestion execution block, then rerun SENSOR-001H.",
            safety_boundary=safety_boundary,
            monitoring_contract=monitoring_contract,
        )

    if metric_summary["inserted_count"] == 0 and metric_summary["duplicate_count"] >= metric_summary["total_loaded"]:
        return Sensor001HMonitoringReport(
            overall_status="monitoring_attention_required_duplicate_dominated",
            source_status=source_status,
            activation_state=activation_state,
            term_observations=term_observations,
            latest_runs=latest_runs,
            metric_summary=metric_summary,
            findings=("Post-activation runs are visible but appear duplicate-dominated.",),
            next_action="Review term quality and overlap before keeping the profile active long-term.",
            safety_boundary=safety_boundary,
            monitoring_contract=monitoring_contract,
        )

    return Sensor001HMonitoringReport(
        overall_status="monitoring_ready_with_observed_runs",
        source_status=source_status,
        activation_state=activation_state,
        term_observations=term_observations,
        latest_runs=latest_runs,
        metric_summary=metric_summary,
        findings=(
            "Post-activation ingestion runs are visible for the controlled BA remote/nationwide profile.",
            "Use this report as input for the next source-quality or activation-retention decision.",
        ),
        next_action="Review observed yield, duplicates, failures, and term contribution before any further activation broadening.",
        safety_boundary=safety_boundary,
        monitoring_contract=monitoring_contract,
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SENSOR-001H BA Remote/Nationwide Post-Activation Monitoring",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- source_status: `{report.get('source_status')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        "",
        "## Activation state",
        "",
    ]
    for key, value in report.get("activation_state", {}).items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Metric summary", ""])
    for key, value in report.get("metric_summary", {}).items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Term observations", ""])
    observations = report.get("term_observations", [])
    if not observations:
        lines.append("- none")
    for observation in observations:
        lines.append(
            f"- {observation.get('search_term')}: runs={observation.get('ingestion_run_count')}, "
            f"loaded={observation.get('total_loaded')}, inserted={observation.get('inserted_count')}, "
            f"duplicates={observation.get('duplicate_count')}, failed={observation.get('failed_run_count')}"
        )

    lines.extend(["", "## Findings", ""])
    for finding in report.get("findings", []):
        lines.append(f"- {finding}")

    lines.extend(["", "## Next action", "", str(report.get("next_action", "")), ""])
    return "\n".join(lines)


def _build_activation_state(
    profiles: tuple[MarketSensorProfileState, ...],
    terms: tuple[MarketSensorTermState, ...],
) -> Sensor001HActivationState:
    review_profiles = tuple(profile for profile in profiles if profile.profile_name == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME)
    if not review_profiles:
        return Sensor001HActivationState(
            profile_id=None,
            profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            source_name=BA_SOURCE_NAME,
            current_is_active=False,
            page_size=None,
            active_terms=(),
            missing_expected_terms=EXPECTED_BA_REMOTE_TERMS,
        )

    profile = review_profiles[0]
    active_terms = tuple(
        sorted(term.search_term for term in terms if term.profile_name == profile.profile_name and term.is_active)
    )
    missing_expected_terms = tuple(term for term in EXPECTED_BA_REMOTE_TERMS if term not in active_terms)
    return Sensor001HActivationState(
        profile_id=profile.id,
        profile_name=profile.profile_name,
        source_name=profile.source_name,
        current_is_active=profile.is_active,
        page_size=profile.page_size,
        active_terms=active_terms,
        missing_expected_terms=missing_expected_terms,
    )


def _summarize(
    term_observations: tuple[Sensor001HTermObservation, ...],
    latest_runs: tuple[Sensor001HLatestRun, ...],
) -> dict[str, Any]:
    ingestion_run_count = sum(observation.ingestion_run_count for observation in term_observations)
    total_loaded = sum(observation.total_loaded for observation in term_observations)
    inserted_count = sum(observation.inserted_count for observation in term_observations)
    duplicate_count = sum(observation.duplicate_count for observation in term_observations)
    raw_jobs_count = sum(observation.raw_jobs_count for observation in term_observations)
    failed_run_count = sum(observation.failed_run_count for observation in term_observations)
    observed_terms = tuple(observation.search_term for observation in term_observations if observation.ingestion_run_count > 0)
    silent_terms = tuple(observation.search_term for observation in term_observations if observation.ingestion_run_count == 0)
    latest_started_at = next((run.started_at for run in latest_runs if run.started_at), None)
    return {
        "ingestion_run_count": ingestion_run_count,
        "total_loaded": total_loaded,
        "inserted_count": inserted_count,
        "duplicate_count": duplicate_count,
        "raw_jobs_count": raw_jobs_count,
        "failed_run_count": failed_run_count,
        "observed_terms": observed_terms,
        "silent_terms": silent_terms,
        "latest_started_at": latest_started_at,
    }


def _safety_boundary() -> dict[str, bool]:
    return {
        "read_only_monitoring": True,
        "external_requests": False,
        "database_reads": True,
        "database_writes": False,
        "profile_activation_write": False,
        "raw_jobs_write": False,
        "ingestion_run_write": False,
        "scheduler_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
        "bronze_silver_gold_mutation": False,
        "productive_activation": False,
    }


def _monitoring_contract() -> dict[str, Any]:
    return {
        "purpose": "Measure the effect of the controlled BA remote/nationwide profile after activation without triggering ingestion.",
        "decision_inputs": (
            "ingestion_run_count",
            "inserted_count",
            "duplicate_count",
            "failed_run_count",
            "term contribution",
        ),
        "not_a_decision": True,
        "next_possible_work_items": (
            "SENSOR-001I BA Remote First Run Review",
            "MARKET-002A Sensor Promotion Quality Review",
            "STEPSTONE-002A Discovery Cycle Quality Review",
        ),
    }


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
