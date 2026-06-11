"""QUALITY-001 Search Intelligence quality and recall foundation.

This module deliberately stays read-only and works on already materialized
reports/read-model objects. It does not execute external searches, write to the
database, promote candidates, mutate gates, activate connectors, or touch the
scheduler.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from src.search_intelligence.market_sensor_funnel import (
    ConnectorCandidate,
    MarketSensorItem,
    companies_without_connector_candidate,
    count_connector_companies_by_status,
    count_market_companies_by_decision,
    summarize_funnel,
)
from src.search_intelligence.stepstone_company_discovery_cycle import StepStoneDiscoveryAssessment


@dataclass(frozen=True)
class QualityFinding:
    finding_id: str
    severity: str
    area: str
    message: str
    recommended_next_action: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AssumptionInventoryEntry:
    assumption_id: str
    area: str
    assumption: str
    risk_type: str
    decision_scope: str
    current_confidence: str
    evidence_required: str
    validation_method: str
    review_status: str
    recheck_trigger: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SensorEffectivenessReview:
    overall_status: str
    ingestion_run_count: int
    total_loaded: int
    inserted_count: int
    duplicate_count: int
    failed_run_count: int
    inserted_share_percent: float
    duplicate_share_percent: float
    observed_terms: tuple[str, ...]
    silent_terms: tuple[str, ...]
    effectiveness_level: str
    findings: tuple[QualityFinding, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "findings": [finding.as_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class MarketFunnelQualityReview:
    market_sensor_companies: int
    connector_candidate_companies: int
    with_connector_candidate: int
    without_connector_candidate: int
    connector_candidate_share_percent: float
    market_companies_by_decision: Mapping[str, int]
    connector_companies_by_status: Mapping[str, int]
    high_priority_gap_count: int
    promotion_gap_count: int
    manual_review_gap_count: int
    funnel_quality_level: str
    findings: tuple[QualityFinding, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "market_companies_by_decision": dict(self.market_companies_by_decision),
            "connector_companies_by_status": dict(self.connector_companies_by_status),
            "findings": [finding.as_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class StepStoneNoveltyReview:
    search_term: str
    observed_count: int
    distinct_company_count: int
    known_cooldown_hit_count: int
    new_company_count: int
    relevance_hits: int
    drift_hits: int
    quality_score: float
    recommended_interval_days: int
    novelty_share_percent: float
    known_company_share_percent: float
    relevance_share_percent: float
    drift_share_percent: float
    saturation_level: str
    findings: tuple[QualityFinding, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "findings": [finding.as_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class Quality001Report:
    sensor_effectiveness: SensorEffectivenessReview | None
    market_funnel_quality: MarketFunnelQualityReview | None
    stepstone_novelty_reviews: tuple[StepStoneNoveltyReview, ...]
    assumption_inventory: tuple[AssumptionInventoryEntry, ...]
    findings: tuple[QualityFinding, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "quality001.search_intelligence_quality.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "work_item": "QUALITY-001 Search Intelligence Quality & Recall Foundation",
            "parallel_subitems": [
                "SENSOR-001I BA Remote Effectiveness Review",
                "MARKET-002A Promotion Funnel Quality",
                "STEPSTONE-002A Discovery Novelty & Saturation Review",
                "ASSUMPTION-001A Assumption Inventory Bootstrap",
            ],
            "safety_boundary": quality001_safety_boundary(),
            "sensor_effectiveness": self.sensor_effectiveness.as_dict() if self.sensor_effectiveness else None,
            "market_funnel_quality": self.market_funnel_quality.as_dict() if self.market_funnel_quality else None,
            "stepstone_novelty_reviews": [review.as_dict() for review in self.stepstone_novelty_reviews],
            "assumption_inventory": [entry.as_dict() for entry in self.assumption_inventory],
            "findings": [finding.as_dict() for finding in self.findings],
            "next_action": suggest_next_quality_action(self.findings),
        }


def quality001_safety_boundary() -> dict[str, bool]:
    return {
        "read_only_quality_review": True,
        "external_requests": False,
        "database_writes": False,
        "database_reads_required": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
        "bronze_silver_gold_mutation": False,
        "scheduler_mutation": False,
        "csv_or_export_as_pipeline_input": False,
    }


def review_sensor_effectiveness(sensor001h_report: Mapping[str, Any]) -> SensorEffectivenessReview:
    summary = sensor001h_report.get("metric_summary", {}) or {}
    ingestion_run_count = _to_int(summary.get("ingestion_run_count"))
    total_loaded = _to_int(summary.get("total_loaded"))
    inserted_count = _to_int(summary.get("inserted_count"))
    duplicate_count = _to_int(summary.get("duplicate_count"))
    failed_run_count = _to_int(summary.get("failed_run_count"))
    inserted_share = _percent(inserted_count, total_loaded)
    duplicate_share = _percent(duplicate_count, total_loaded)
    observed_terms = _tuple_text(summary.get("observed_terms"))
    silent_terms = _tuple_text(summary.get("silent_terms"))
    findings: list[QualityFinding] = []

    if ingestion_run_count == 0:
        effectiveness = "awaiting_first_run"
        findings.append(_finding("SENSOR-001I-001", "medium", "sensor_effectiveness", "No BA remote/nationwide run is visible yet.", "Wait for the approved scheduler/run path, then rerun SENSOR-001H and QUALITY-001."))
    elif failed_run_count > 0:
        effectiveness = "blocked_by_failed_runs"
        findings.append(_finding("SENSOR-001I-002", "high", "sensor_effectiveness", "At least one BA remote/nationwide run failed.", "Inspect failed runs before interpreting recall or source quality."))
    elif inserted_count == 0 and duplicate_count >= total_loaded:
        effectiveness = "duplicate_dominated"
        findings.append(_finding("SENSOR-001I-003", "high", "sensor_effectiveness", "BA remote/nationwide output is duplicate-dominated and has no new inserts.", "Review term overlap and duplicate provenance before keeping or broadening the profile."))
    elif inserted_share < 25.0 and total_loaded > 0:
        effectiveness = "low_incremental_yield"
        findings.append(_finding("SENSOR-001I-004", "medium", "sensor_effectiveness", "BA remote/nationwide output has low incremental inserted share.", "Compare duplicate provenance and term contribution before deciding whether the sensor deserves continued priority."))
    else:
        effectiveness = "observed_incremental_yield"
        findings.append(_finding("SENSOR-001I-005", "info", "sensor_effectiveness", "BA remote/nationwide output shows observable incremental yield.", "Use company uniqueness and Silver relevance checks before further expansion."))

    if silent_terms:
        findings.append(_finding("SENSOR-001I-006", "medium", "sensor_effectiveness", "At least one configured term has no visible ingestion run.", "Check scheduler/profile term coverage before judging search-term quality."))

    return SensorEffectivenessReview(
        overall_status=str(sensor001h_report.get("overall_status") or "unknown"),
        ingestion_run_count=ingestion_run_count,
        total_loaded=total_loaded,
        inserted_count=inserted_count,
        duplicate_count=duplicate_count,
        failed_run_count=failed_run_count,
        inserted_share_percent=inserted_share,
        duplicate_share_percent=duplicate_share,
        observed_terms=observed_terms,
        silent_terms=silent_terms,
        effectiveness_level=effectiveness,
        findings=tuple(findings),
    )


def review_market_funnel_quality(
    market_items: Iterable[MarketSensorItem],
    connector_candidates: Iterable[ConnectorCandidate],
) -> MarketFunnelQualityReview:
    market_tuple = tuple(market_items)
    candidate_tuple = tuple(connector_candidates)
    summary = summarize_funnel(market_tuple, candidate_tuple)
    gaps = companies_without_connector_candidate(market_tuple, candidate_tuple)
    high_priority_gaps = [gap for gap in gaps if gap.max_priority >= 80]
    promotion_gaps = [gap for gap in gaps if gap.suggested_funnel_action == "promotion_gap_create_candidate_recommended"]
    manual_review_gaps = [gap for gap in gaps if gap.suggested_funnel_action == "promotion_gap_manual_review_required"]
    findings: list[QualityFinding] = []

    if summary.market_sensor_companies == 0:
        quality_level = "no_market_sensor_signal"
        findings.append(_finding("MARKET-002A-001", "medium", "market_funnel", "No market-sensor companies are available for funnel quality review.", "Record or load market observations before interpreting recall quality."))
    elif promotion_gaps:
        quality_level = "promotion_gap_visible"
        findings.append(_finding("MARKET-002A-002", "high", "market_funnel", "Market observations recommend candidate creation but no connector candidate exists yet.", "Review promotion gaps before changing gates or adding more sensors."))
    elif high_priority_gaps:
        quality_level = "high_priority_gap_visible"
        findings.append(_finding("MARKET-002A-003", "medium", "market_funnel", "High-priority observed companies have not reached the connector candidate funnel.", "Inspect linkage and promotion evidence for high-priority gaps."))
    elif summary.without_connector_candidate > 0:
        quality_level = "residual_gap_visible"
        findings.append(_finding("MARKET-002A-004", "info", "market_funnel", "Some observed companies have not reached the connector candidate funnel.", "Track residual gaps and recheck after the next promotion review."))
    else:
        quality_level = "no_current_funnel_gap"
        findings.append(_finding("MARKET-002A-005", "info", "market_funnel", "All market-observed companies have a connector-candidate linkage.", "Continue monitoring for stale or low-quality candidate states."))

    return MarketFunnelQualityReview(
        market_sensor_companies=summary.market_sensor_companies,
        connector_candidate_companies=summary.connector_candidate_companies,
        with_connector_candidate=summary.with_connector_candidate,
        without_connector_candidate=summary.without_connector_candidate,
        connector_candidate_share_percent=summary.connector_candidate_share_percent,
        market_companies_by_decision=count_market_companies_by_decision(market_tuple),
        connector_companies_by_status=count_connector_companies_by_status(candidate_tuple),
        high_priority_gap_count=len(high_priority_gaps),
        promotion_gap_count=len(promotion_gaps),
        manual_review_gap_count=len(manual_review_gaps),
        funnel_quality_level=quality_level,
        findings=tuple(findings),
    )


def review_stepstone_novelty(assessment: StepStoneDiscoveryAssessment) -> StepStoneNoveltyReview:
    observed = assessment.observed_count
    novelty_share = _percent(assessment.new_company_count, max(assessment.distinct_company_count, 1)) if assessment.distinct_company_count else 0.0
    known_share = _percent(assessment.known_cooldown_hit_count, observed)
    relevance_share = _percent(assessment.relevance_hits, observed)
    drift_share = _percent(assessment.drift_hits, observed)
    findings: list[QualityFinding] = []

    if observed == 0:
        saturation = "empty_result_or_overconstrained"
        findings.append(_finding("STEPSTONE-002A-001", "medium", "stepstone_novelty", "StepStone discovery assessment has no observations.", "Check whether the NOT wave over-constrained the query or the search space is saturated."))
    elif assessment.new_company_count == 0:
        saturation = "no_novel_company_signal"
        findings.append(_finding("STEPSTONE-002A-002", "high", "stepstone_novelty", "StepStone discovery produced no new company signal.", "Review cooldown/suppression loop before adding more search terms."))
    elif known_share >= 50.0:
        saturation = "known_company_dominated"
        findings.append(_finding("STEPSTONE-002A-003", "medium", "stepstone_novelty", "StepStone discovery remains dominated by known companies.", "Rotate exclusion waves or inspect company-key/cooldown matching."))
    elif drift_share > relevance_share:
        saturation = "drift_dominated"
        findings.append(_finding("STEPSTONE-002A-004", "medium", "stepstone_novelty", "StepStone discovery has more drift than relevance signal.", "Keep the term on a longer cycle and avoid promotion until evidence improves."))
    else:
        saturation = "novelty_signal_visible"
        findings.append(_finding("STEPSTONE-002A-005", "info", "stepstone_novelty", "StepStone discovery shows visible novelty signal.", "Use downstream candidate evidence checks before promotion."))

    return StepStoneNoveltyReview(
        search_term=assessment.search_term,
        observed_count=observed,
        distinct_company_count=assessment.distinct_company_count,
        known_cooldown_hit_count=assessment.known_cooldown_hit_count,
        new_company_count=assessment.new_company_count,
        relevance_hits=assessment.relevance_hits,
        drift_hits=assessment.drift_hits,
        quality_score=assessment.quality_score,
        recommended_interval_days=assessment.recommended_interval_days,
        novelty_share_percent=novelty_share,
        known_company_share_percent=known_share,
        relevance_share_percent=relevance_share,
        drift_share_percent=drift_share,
        saturation_level=saturation,
        findings=tuple(findings),
    )


def bootstrap_assumption_inventory() -> tuple[AssumptionInventoryEntry, ...]:
    return (
        AssumptionInventoryEntry(
            assumption_id="ASSUMPTION-001A-BA-REMOTE-INCREMENTAL-VALUE",
            area="sensor_effectiveness",
            assumption="BA remote/nationwide coverage adds useful incremental market signal beyond existing Hannover/local BA coverage.",
            risk_type="false_positive_operational_cost_and_false_negative_blind_spot",
            decision_scope="heuristic_review_only_until_validated",
            current_confidence="unvalidated_to_partial",
            evidence_required="Inserted share, duplicate provenance, distinct company novelty, and downstream Silver relevance for BA remote runs.",
            validation_method="Run SENSOR-001H followed by QUALITY-001 after bounded scheduled runs; compare term and company contribution.",
            review_status="open",
            recheck_trigger="After each controlled BA remote monitoring window or before activation broadening.",
        ),
        AssumptionInventoryEntry(
            assumption_id="ASSUMPTION-001A-STEPSTONE-SUPPRESSION-NOVELTY",
            area="stepstone_novelty",
            assumption="Temporary known-company suppression reveals additional useful employer-origin candidates instead of only hiding relevant recurring employers.",
            risk_type="false_negative_if_suppression_hides_relevant_signal",
            decision_scope="heuristic_discovery_only",
            current_confidence="unvalidated_to_partial",
            evidence_required="New-company count, known-hit ratio, relevance/drift ratio, and later candidate promotion outcome per search term cycle.",
            validation_method="Review STEPSTONE-002A novelty metrics across repeated discovery cycles and compare with market observations.",
            review_status="open",
            recheck_trigger="When novelty share drops, known-company share dominates, or a search term interval is changed.",
        ),
        AssumptionInventoryEntry(
            assumption_id="ASSUMPTION-001A-MARKET-PROMOTION-RECALL",
            area="market_funnel",
            assumption="Market-sensor observations with sufficient evidence are not silently lost before reaching employer-origin candidate review.",
            risk_type="false_negative_candidate_loss",
            decision_scope="quality_control_and_review_prioritization",
            current_confidence="partial",
            evidence_required="Promotion gap counts, manual-review gap counts, high-priority unlinked companies, and stale known-candidate linkage checks.",
            validation_method="Run MARKET-002A funnel quality review after market observation and candidate-promotion batches.",
            review_status="open",
            recheck_trigger="After new manual market observations, promotion batches, or changes to candidate linkage logic.",
        ),
        AssumptionInventoryEntry(
            assumption_id="ASSUMPTION-001A-QUALITY-METRICS-NOT-GATE-TRUTH",
            area="governance",
            assumption="QUALITY-001 metrics are diagnostic signals and must not replace gate evidence or final candidate decisions.",
            risk_type="false_positive_decision_shortcut",
            decision_scope="diagnostic_only_not_gate_truth",
            current_confidence="governance_rule",
            evidence_required="Documentation and tests showing report boundaries and no mutation side effects.",
            validation_method="Keep QUALITY-001 read-only and assert safety boundary in tests.",
            review_status="accepted_boundary",
            recheck_trigger="Before using QUALITY-001 output in UI actions, gate decisions, or dashboards.",
        ),
    )


def build_quality001_report(
    *,
    sensor001h_report: Mapping[str, Any] | None = None,
    market_items: Iterable[MarketSensorItem] = (),
    connector_candidates: Iterable[ConnectorCandidate] = (),
    stepstone_assessments: Iterable[StepStoneDiscoveryAssessment] = (),
) -> Quality001Report:
    sensor_review = review_sensor_effectiveness(sensor001h_report) if sensor001h_report else None
    market_tuple = tuple(market_items)
    candidate_tuple = tuple(connector_candidates)
    market_review = review_market_funnel_quality(market_tuple, candidate_tuple) if market_tuple or candidate_tuple else None
    stepstone_reviews = tuple(review_stepstone_novelty(assessment) for assessment in stepstone_assessments)
    findings = tuple(
        finding
        for group in (
            sensor_review.findings if sensor_review else (),
            market_review.findings if market_review else (),
            *(review.findings for review in stepstone_reviews),
        )
        for finding in group
    )
    return Quality001Report(
        sensor_effectiveness=sensor_review,
        market_funnel_quality=market_review,
        stepstone_novelty_reviews=stepstone_reviews,
        assumption_inventory=bootstrap_assumption_inventory(),
        findings=findings,
    )


def suggest_next_quality_action(findings: Iterable[QualityFinding]) -> str:
    finding_tuple = tuple(findings)
    if any(finding.severity == "high" and finding.area == "sensor_effectiveness" for finding in finding_tuple):
        return "resolve_sensor_effectiveness_blocker_before_broadening_search_intelligence"
    if any(finding.severity == "high" and finding.area == "market_funnel" for finding in finding_tuple):
        return "review_market_promotion_gaps_before_new_sensor_expansion"
    if any(finding.severity == "high" and finding.area == "stepstone_novelty" for finding in finding_tuple):
        return "repair_or_reassess_stepstone_discovery_loop_before_more_terms"
    if finding_tuple:
        return "review_quality_findings_then_select_next_search_intelligence_patch"
    return "run_quality001_with_current_sensor_funnel_and_stepstone_inputs"


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# QUALITY-001 Search Intelligence Quality & Recall Foundation",
        "",
        f"- schema_version: `{report.get('schema_version')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- work_item: `{report.get('work_item')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")

    sensor = report.get("sensor_effectiveness")
    lines.extend(["", "## SENSOR-001I BA Remote Effectiveness", ""])
    if sensor:
        lines.extend([
            f"- effectiveness_level: `{sensor.get('effectiveness_level')}`",
            f"- ingestion_run_count: `{sensor.get('ingestion_run_count')}`",
            f"- total_loaded: `{sensor.get('total_loaded')}`",
            f"- inserted_share_percent: `{sensor.get('inserted_share_percent')}`",
            f"- duplicate_share_percent: `{sensor.get('duplicate_share_percent')}`",
        ])
    else:
        lines.append("- not evaluated in this report")

    market = report.get("market_funnel_quality")
    lines.extend(["", "## MARKET-002A Promotion Funnel Quality", ""])
    if market:
        lines.extend([
            f"- funnel_quality_level: `{market.get('funnel_quality_level')}`",
            f"- market_sensor_companies: `{market.get('market_sensor_companies')}`",
            f"- connector_candidate_share_percent: `{market.get('connector_candidate_share_percent')}`",
            f"- promotion_gap_count: `{market.get('promotion_gap_count')}`",
            f"- manual_review_gap_count: `{market.get('manual_review_gap_count')}`",
        ])
    else:
        lines.append("- not evaluated in this report")

    lines.extend(["", "## STEPSTONE-002A Discovery Novelty", ""])
    stepstone_reviews = report.get("stepstone_novelty_reviews", [])
    if stepstone_reviews:
        for review in stepstone_reviews:
            lines.append(
                f"- {review.get('search_term')}: saturation=`{review.get('saturation_level')}`, "
                f"novelty={review.get('novelty_share_percent')}%, quality={review.get('quality_score')}"
            )
    else:
        lines.append("- not evaluated in this report")

    lines.extend(["", "## ASSUMPTION-001A Bootstrap", ""])
    for assumption in report.get("assumption_inventory", []):
        lines.append(
            f"- {assumption.get('assumption_id')}: {assumption.get('review_status')} "
            f"({assumption.get('decision_scope')})"
        )

    lines.extend(["", "## Findings", ""])
    findings = report.get("findings", [])
    if findings:
        for finding in findings:
            lines.append(
                f"- [{finding.get('severity')}] {finding.get('finding_id')} / {finding.get('area')}: "
                f"{finding.get('message')}"
            )
    else:
        lines.append("- none; run with current report/read-model inputs for a concrete quality review")

    lines.extend(["", "## Next action", "", str(report.get("next_action", "")), ""])
    return "\n".join(lines)


def _finding(finding_id: str, severity: str, area: str, message: str, recommended_next_action: str) -> QualityFinding:
    return QualityFinding(
        finding_id=finding_id,
        severity=severity,
        area=area,
        message=message,
        recommended_next_action=recommended_next_action,
    )


def _to_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(value)


def _percent(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(100.0 * part / total, 2)


def _tuple_text(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    return tuple(str(item) for item in value if str(item))
