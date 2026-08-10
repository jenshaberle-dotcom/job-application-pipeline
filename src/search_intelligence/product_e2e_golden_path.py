"""Generic discovery-to-Top-5 golden-path audit contracts.

Discovery provenance controls only how a case enters the audit. Every identified
employer then uses the same downstream stages and decision rules. Company names
and IDs are evidence labels, never control-flow inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from src.search_intelligence.origin_seed_pool import ObservationSeed, normalize_text

AUDIT_BOUNDARY = {
    "read_only_database": True,
    "review_output_only_not_pipeline_input": True,
    "no_external_requests": True,
    "no_candidate_creation": True,
    "no_candidate_or_gate_mutation": True,
    "no_connector_artifact_generation": True,
    "no_connector_registration": True,
    "no_source_activation": True,
    "no_bronze_or_silver_write": True,
    "no_scheduler_change": True,
    "no_ranking_policy_change": True,
    "no_application_action": True,
    "company_specific_branching_forbidden": True,
}

STAGE_ORDER = (
    "discovery_signal",
    "employer_identity",
    "origin_candidate",
    "origin_url",
    "origin_inventory",
    "connector_build",
    "source_activation",
    "job_ingestion",
    "silver_job",
    "product_assessment",
    "top5_serving",
)

PRIMARY_SOURCE_CLASSES = (
    "aggregator_company_discovery",
    "public_job_api_discovery",
    "manual_observation",
)
PASSING_STATUSES = {"passed", "valid_stop"}


@dataclass(frozen=True)
class DiscoveryCase:
    case_id: str
    discovery_source_class: str
    seed_type: str
    seed_source_table: str
    company_key: str | None
    company_name: str | None
    source_name: str | None
    seed_url: str | None
    priority_score: float
    prior_reason: str


@dataclass(frozen=True)
class GateState:
    gate_name: str
    gate_status: str
    decision: str | None = None
    stop_reason: str | None = None


@dataclass(frozen=True)
class LifecycleSnapshot:
    candidate_id: int | None = None
    canonical_company_name: str | None = None
    source_name_candidate: str | None = None
    candidate_status: str | None = None
    candidate_url: str | None = None
    current_stage: str | None = None
    blocking_gate: str | None = None
    blocking_gate_status: str | None = None
    blocker_reason: str | None = None
    generation_status: str | None = None
    build_status: str | None = None
    queue_action: str | None = None
    queue_reason: str | None = None
    gate_states: Mapping[str, GateState] = field(default_factory=dict)
    source_raw_job_count: int | None = None
    silver_job_count: int = 0
    product_readiness_counts: Mapping[str, int] = field(default_factory=dict)
    top5_job_count: int = 0


@dataclass(frozen=True)
class StageResult:
    stage: str
    status: str
    reason_code: str
    reason: str
    operator_decision: str | None = None
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseTrace:
    case: DiscoveryCase
    stages: tuple[StageResult, ...]
    overall_status: str
    next_blocker_stage: str | None


@dataclass(frozen=True)
class GapSummary:
    stage: str
    status: str
    reason_code: str
    occurrence_count: int
    discovery_source_classes: tuple[str, ...]
    scope: str


def discovery_source_class(seed: ObservationSeed) -> str:
    """Map one seed to a source-neutral ingress class."""

    source_name = normalize_text(seed.source_name)
    if seed.seed_type == "aggregator_company_seed":
        return "aggregator_company_discovery"
    if source_name in {"bundesagentur_fuer_arbeit", "ba"}:
        return "public_job_api_discovery"
    if seed.seed_type == "job_text_signal_seed":
        return "public_job_api_discovery"
    if "manual" in source_name or seed.seed_source_table == "manual_market_observation":
        return "manual_observation"
    if seed.seed_type in {"origin_url_seed", "ats_structure_seed"}:
        return "existing_origin_evidence"
    return "other_discovery"


def case_from_seed(seed: ObservationSeed) -> DiscoveryCase:
    return DiscoveryCase(
        case_id=seed.seed_key,
        discovery_source_class=discovery_source_class(seed),
        seed_type=seed.seed_type,
        seed_source_table=seed.seed_source_table,
        company_key=seed.company_key,
        company_name=seed.company_name,
        source_name=seed.source_name,
        seed_url=seed.seed_url,
        priority_score=seed.priority_score,
        prior_reason=seed.prior_reason,
    )


def _case_identity(case: DiscoveryCase) -> str:
    return case.company_key or normalize_text(case.company_name) or case.case_id


def _selection_key(case: DiscoveryCase) -> tuple[object, ...]:
    missing_identity = not bool(case.company_key or case.company_name)
    return (
        missing_identity,
        -case.priority_score,
        case.discovery_source_class,
        case.company_key or "",
        case.case_id,
    )


def select_representative_cases(
    cases: Iterable[DiscoveryCase],
    *,
    limit: int = 5,
    preferred_source_classes: Sequence[str] = PRIMARY_SOURCE_CLASSES,
) -> list[DiscoveryCase]:
    """Select a bounded, source-diverse portfolio without company allowlists.

    Deduplication happens first within each source class. This preserves evidence
    that the same employer was independently found by StepStone, BA or a manual
    observation. Final portfolio selection still includes an employer at most once.
    """

    if limit < 1 or limit > 5:
        raise ValueError("limit must be between 1 and 5")

    best_by_source_identity: dict[tuple[str, str], DiscoveryCase] = {}
    for case in cases:
        key = (case.discovery_source_class, _case_identity(case))
        current = best_by_source_identity.get(key)
        if current is None or _selection_key(case) < _selection_key(current):
            best_by_source_identity[key] = case

    ranked = sorted(best_by_source_identity.values(), key=_selection_key)
    selected: list[DiscoveryCase] = []
    selected_identities: set[str] = set()

    for source_class in preferred_source_classes:
        candidate = next(
            (
                item
                for item in ranked
                if item.discovery_source_class == source_class
                and _case_identity(item) not in selected_identities
            ),
            None,
        )
        if candidate is not None:
            selected.append(candidate)
            selected_identities.add(_case_identity(candidate))
        if len(selected) == limit:
            return selected

    for candidate in ranked:
        identity = _case_identity(candidate)
        if identity in selected_identities:
            continue
        selected.append(candidate)
        selected_identities.add(identity)
        if len(selected) == limit:
            break
    return selected


def _gate(snapshot: LifecycleSnapshot, name: str) -> GateState | None:
    return snapshot.gate_states.get(name)


def _passed_gate(snapshot: LifecycleSnapshot, name: str) -> bool:
    gate = _gate(snapshot, name)
    return bool(gate and gate.gate_status == "passed")


def _upstream_blocking_gate(
    snapshot: LifecycleSnapshot,
) -> tuple[str, str] | None:
    """Return a concrete pre-detail blocking gate that the audit must preserve."""

    gate_name = snapshot.blocking_gate
    gate_status = snapshot.blocking_gate_status
    if not gate_name or gate_name == "detail_evidence_gate" or not gate_status:
        return None
    if gate_status not in {"manual_review_required", "failed", "deferred"}:
        return None
    return gate_name, gate_status


def _stage(
    stage: str,
    status: str,
    reason_code: str,
    reason: str,
    *,
    operator_decision: str | None = None,
    evidence: Mapping[str, object] | None = None,
) -> StageResult:
    return StageResult(
        stage=stage,
        status=status,
        reason_code=reason_code,
        reason=reason,
        operator_decision=operator_decision,
        evidence=evidence or {},
    )


def _finish(case: DiscoveryCase, stages: list[StageResult]) -> CaseTrace:
    blocker = next((item.stage for item in stages if item.status not in PASSING_STATUSES), None)
    if blocker is None:
        overall = "completed"
    elif any(item.status == "operator_decision_required" for item in stages):
        overall = "operator_decision_required"
    else:
        overall = "blocked"
    return CaseTrace(
        case=case,
        stages=tuple(stages),
        overall_status=overall,
        next_blocker_stage=blocker,
    )


def trace_case(case: DiscoveryCase, snapshot: LifecycleSnapshot) -> CaseTrace:
    """Trace one case with rules that are independent of company identity."""

    stages = [
        _stage(
            "discovery_signal",
            "passed",
            "discovery_signal_present",
            "A bounded discovery or observation signal exists.",
            evidence={
                "source_class": case.discovery_source_class,
                "seed_type": case.seed_type,
            },
        )
    ]

    if not (case.company_key or case.company_name):
        stages.append(
            _stage(
                "employer_identity",
                "capability_gap",
                "normalized_employer_identity_missing",
                "The discovery signal is not linked to a normalized employer identity.",
            )
        )
        return _finish(case, stages)

    stages.append(
        _stage(
            "employer_identity",
            "passed",
            "normalized_employer_identity_present",
            "The discovery signal contains a normalized employer identity.",
        )
    )

    if snapshot.candidate_id is None:
        stages.append(
            _stage(
                "origin_candidate",
                "capability_gap",
                "origin_candidate_missing",
                "No employer-origin candidate is linked to the discovered employer.",
            )
        )
        return _finish(case, stages)

    stages.append(
        _stage(
            "origin_candidate",
            "passed",
            "origin_candidate_present",
            "A reusable employer-origin candidate exists.",
            evidence={
                "candidate_id": snapshot.candidate_id,
                "canonical_company_name": snapshot.canonical_company_name,
                "candidate_status": snapshot.candidate_status,
            },
        )
    )

    if not snapshot.candidate_url:
        manual = snapshot.blocking_gate_status == "manual_review_required"
        stages.append(
            _stage(
                "origin_url",
                "operator_decision_required" if manual else "missing_evidence",
                "origin_url_missing",
                snapshot.blocker_reason
                or "No validated origin URL is persisted for the candidate.",
                operator_decision=(
                    "Choose among materially non-equivalent origin candidates; do not "
                    "choose merely because a URL is reachable."
                    if manual
                    else None
                ),
            )
        )
        return _finish(case, stages)

    stages.append(
        _stage(
            "origin_url",
            "passed",
            "origin_url_persisted",
            "A candidate origin URL is persisted.",
            evidence={"candidate_url": snapshot.candidate_url},
        )
    )

    inventory_gate = _gate(snapshot, "detail_evidence_gate")
    inventory_passed = (
        snapshot.candidate_status == "active_controlled"
        or _passed_gate(snapshot, "detail_evidence_gate")
        or bool(snapshot.product_readiness_counts)
    )
    if not inventory_passed:
        upstream_blocker = _upstream_blocking_gate(snapshot)
        if upstream_blocker is not None:
            blocking_gate, blocking_status = upstream_blocker
            manual = blocking_status == "manual_review_required"
            stages.append(
                _stage(
                    "origin_inventory",
                    "operator_decision_required" if manual else "missing_evidence",
                    f"{blocking_gate}_{blocking_status}",
                    snapshot.blocker_reason
                    or (
                        f"Upstream employer-origin gate {blocking_gate!r} is "
                        f"{blocking_status!r}; origin inventory must not be inferred past it."
                    ),
                    operator_decision=(
                        "Resolve the explicit upstream employer-origin manual-review gate "
                        "before treating origin inventory as missing evidence."
                        if manual
                        else None
                    ),
                    evidence={
                        "blocking_gate": blocking_gate,
                        "blocking_gate_status": blocking_status,
                        "current_stage": snapshot.current_stage,
                    },
                )
            )
            return _finish(case, stages)

        manual = bool(
            inventory_gate and inventory_gate.gate_status == "manual_review_required"
        )
        stages.append(
            _stage(
                "origin_inventory",
                "operator_decision_required" if manual else "missing_evidence",
                "origin_inventory_unproven",
                (inventory_gate.stop_reason if inventory_gate else None)
                or "Relevant job inventory or concrete detail evidence is not proven.",
                operator_decision=(
                    "Resolve source-family equivalence or multi-origin coverage when "
                    "evidence cannot decide."
                    if manual
                    else None
                ),
            )
        )
        return _finish(case, stages)

    stages.append(
        _stage(
            "origin_inventory",
            "passed",
            "origin_inventory_proven",
            "Relevant origin inventory or equivalent concrete job evidence is proven.",
        )
    )

    if snapshot.candidate_status == "active_controlled":
        stages.append(
            _stage(
                "connector_build",
                "passed",
                "connector_available",
                "The candidate is backed by a controlled active connector/source.",
            )
        )
    elif snapshot.build_status == "artifacts_present":
        stages.append(
            _stage(
                "connector_build",
                "passed",
                "connector_artifacts_present",
                "Connector artifacts exist and can proceed to activation review.",
            )
        )
    elif snapshot.build_status in {
        "build_approval_required",
        "artifact_generation_allowed",
    }:
        approval_required = snapshot.build_status == "build_approval_required"
        stages.append(
            _stage(
                "connector_build",
                "operator_decision_required" if approval_required else "missing_evidence",
                str(snapshot.build_status),
                snapshot.queue_reason
                or "Connector build is waiting at its controlled build boundary.",
                operator_decision=(
                    "Approve bounded connector artifact generation."
                    if approval_required
                    else None
                ),
            )
        )
        return _finish(case, stages)
    else:
        stages.append(
            _stage(
                "connector_build",
                "capability_gap",
                "connector_build_not_reached",
                snapshot.queue_reason
                or "No validated connector build path is currently available.",
            )
        )
        return _finish(case, stages)

    if snapshot.candidate_status != "active_controlled":
        stages.append(
            _stage(
                "source_activation",
                "operator_decision_required",
                "source_activation_approval_required",
                "Connector artifacts do not authorize registration or source activation.",
                operator_decision=(
                    "Approve connector registration and a separate controlled source "
                    "activation."
                ),
            )
        )
        return _finish(case, stages)

    stages.append(
        _stage(
            "source_activation",
            "passed",
            "source_active_controlled",
            "The source is active under controlled operation.",
            evidence={"source_name_candidate": snapshot.source_name_candidate},
        )
    )

    if (snapshot.source_raw_job_count or 0) > 0 or snapshot.silver_job_count > 0:
        stages.append(
            _stage(
                "job_ingestion",
                "passed",
                "ingested_job_evidence_present",
                "An exact active-source Raw job or downstream Silver job proves ingestion.",
                evidence={
                    "source_raw_job_count": snapshot.source_raw_job_count,
                    "silver_job_count": snapshot.silver_job_count,
                },
            )
        )
    else:
        stages.append(
            _stage(
                "job_ingestion",
                "capability_gap",
                "active_source_without_ingested_job",
                "The source is active but no ingested job is linked to this employer.",
            )
        )
        return _finish(case, stages)

    if snapshot.silver_job_count <= 0:
        stages.append(
            _stage(
                "silver_job",
                "capability_gap",
                "silver_normalization_missing",
                "Raw ingestion exists but no normalized Silver job is available.",
            )
        )
        return _finish(case, stages)

    stages.append(
        _stage(
            "silver_job",
            "passed",
            "silver_job_present",
            "At least one normalized Silver job is available.",
            evidence={"silver_job_count": snapshot.silver_job_count},
        )
    )

    if not snapshot.product_readiness_counts:
        stages.append(
            _stage(
                "product_assessment",
                "capability_gap",
                "product_assessment_missing",
                "Silver jobs exist but Product V1 readiness has not been assessed.",
            )
        )
        return _finish(case, stages)

    review_statuses = {
        "origin_validation_required",
        "activity_evidence_required",
        "hard_filter_decision_required",
    }.intersection(snapshot.product_readiness_counts)
    stages.append(
        _stage(
            "product_assessment",
            "operator_decision_required" if review_statuses else "passed",
            (
                "product_assessment_requires_review"
                if review_statuses
                else "product_assessment_present"
            ),
            (
                "Product assessment exists but required evidence needs operator review."
                if review_statuses
                else "Product readiness and blocking reasons are available."
            ),
            operator_decision=(
                "Resolve only explicitly unknown origin, activity or hard-filter facts."
                if review_statuses
                else None
            ),
            evidence={
                "readiness_counts": dict(snapshot.product_readiness_counts),
                "review_statuses": sorted(review_statuses),
            },
        )
    )
    if review_statuses:
        return _finish(case, stages)

    if snapshot.top5_job_count > 0:
        stages.append(
            _stage(
                "top5_serving",
                "passed",
                "top5_job_present",
                "At least one job is served by the approved Top-5 view.",
                evidence={"top5_job_count": snapshot.top5_job_count},
            )
        )
    elif snapshot.product_readiness_counts.get("rankable", 0) > 0:
        stages.append(
            _stage(
                "top5_serving",
                "valid_stop",
                "rankable_but_not_in_top5",
                "The job is rankable but outside the current bounded Top-5.",
            )
        )
    else:
        stages.append(
            _stage(
                "top5_serving",
                "valid_stop",
                "no_eligible_top5_job",
                "The chain completed, but no job currently qualifies for Top-5.",
            )
        )
    return _finish(case, stages)


def summarize_gaps(traces: Iterable[CaseTrace]) -> list[GapSummary]:
    buckets: dict[tuple[str, str, str], dict[str, object]] = {}
    for trace in traces:
        for stage in trace.stages:
            if stage.status in PASSING_STATUSES:
                continue
            key = (stage.stage, stage.status, stage.reason_code)
            bucket = buckets.setdefault(key, {"count": 0, "sources": set()})
            bucket["count"] = int(bucket["count"]) + 1
            sources = bucket["sources"]
            assert isinstance(sources, set)
            sources.add(trace.case.discovery_source_class)

    summaries = []
    for (stage, status, reason_code), bucket in buckets.items():
        sources = tuple(sorted(str(value) for value in bucket["sources"]))
        occurrence_count = int(bucket["count"])
        if len(sources) >= 2:
            scope = "generic_cross_source_gap"
        elif occurrence_count >= 2:
            scope = "source_class_gap"
        else:
            scope = "case_evidence_gap"
        summaries.append(
            GapSummary(
                stage=stage,
                status=status,
                reason_code=reason_code,
                occurrence_count=occurrence_count,
                discovery_source_classes=sources,
                scope=scope,
            )
        )
    return sorted(
        summaries,
        key=lambda item: (
            STAGE_ORDER.index(item.stage),
            -item.occurrence_count,
            item.reason_code,
        ),
    )


def stage_status_counts(traces: Iterable[CaseTrace]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {stage: {} for stage in STAGE_ORDER}
    for trace in traces:
        for result in trace.stages:
            stage_counts = counts[result.stage]
            stage_counts[result.status] = stage_counts.get(result.status, 0) + 1
    return {
        stage: dict(sorted(values.items()))
        for stage, values in counts.items()
        if values
    }
