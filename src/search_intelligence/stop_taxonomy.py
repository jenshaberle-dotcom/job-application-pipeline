"""STOP-002 stop taxonomy and repair-strategy registry.

This module is the canonical lookup surface for pipeline stop interpretation.
It deliberately does not inspect the database or execute repair actions.  It
answers three product questions for every known stop category:

1. Is this a good safety stop, a review stop or a likely false-negative risk?
2. Which repair strategy, if any, is safe to plan next?
3. Which safety zone and human-review boundary applies?

The actual classifiers may still use local gate/evidence heuristics.  Once a
classifier chooses a category, the category must resolve through this registry
instead of each caller inventing its own repair semantics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class StopRepairStrategy:
    """A bounded strategy that may be recommended after a stop classification."""

    strategy_id: str
    label: str
    safety_zone: str
    default_next_safe_action: str
    dry_run_required: bool
    explicit_apply_required: bool
    human_review_required: bool
    execution_boundary: str
    will_not: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["will_not"] = list(self.will_not)
        return payload


@dataclass(frozen=True)
class StopTaxonomyEntry:
    """Canonical interpretation of one stop category."""

    category: str
    lifecycle_class: str
    severity: str
    terminal: bool
    default_reprocess: str
    false_negative_risk: str
    repair_strategy_id: str
    description: str
    good_stop_when: str
    false_negative_risk_when: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


NO_WRITE_BOUNDARY = (
    "connector artifacts",
    "connector registrations",
    "source activation",
    "Bronze/Silver data",
    "scheduler configuration",
)

REPAIR_STRATEGIES: dict[str, StopRepairStrategy] = {
    "no_repair_not_stop": StopRepairStrategy(
        strategy_id="no_repair_not_stop",
        label="No repair needed",
        safety_zone="SZ0_READ_ONLY",
        default_next_safe_action="not_applicable",
        dry_run_required=False,
        explicit_apply_required=False,
        human_review_required=False,
        execution_boundary="Read-only display/reporting boundary.",
        will_not=NO_WRITE_BOUNDARY,
    ),
    "bounded_source_url_recovery": StopRepairStrategy(
        strategy_id="bounded_source_url_recovery",
        label="Bounded source URL recovery",
        safety_zone="SZ1_CANDIDATE_METADATA",
        default_next_safe_action="run_source_url_recovery_plan",
        dry_run_required=True,
        explicit_apply_required=True,
        human_review_required=False,
        execution_boundary="May recover or validate candidate source URL metadata only after explicit apply.",
        will_not=NO_WRITE_BOUNDARY,
    ),
    "bounded_relevance_evidence_discovery": StopRepairStrategy(
        strategy_id="bounded_relevance_evidence_discovery",
        label="Bounded relevance evidence discovery",
        safety_zone="SZ2_EVIDENCE_AND_GATES",
        default_next_safe_action="run_relevance_evidence_discovery_plan",
        dry_run_required=True,
        explicit_apply_required=True,
        human_review_required=False,
        execution_boundary="May collect bounded evidence and refresh relevance gate evidence only under review/apply control.",
        will_not=NO_WRITE_BOUNDARY,
    ),
    "bounded_detail_evidence_discovery": StopRepairStrategy(
        strategy_id="bounded_detail_evidence_discovery",
        label="Bounded detail evidence discovery",
        safety_zone="SZ2_EVIDENCE_AND_GATES",
        default_next_safe_action="run_detail_evidence_discovery_plan",
        dry_run_required=True,
        explicit_apply_required=True,
        human_review_required=False,
        execution_boundary="May collect bounded concrete job/detail evidence and update evidence/gate state only under review/apply control.",
        will_not=NO_WRITE_BOUNDARY,
    ),
    "operator_review_triage": StopRepairStrategy(
        strategy_id="operator_review_triage",
        label="Operator review triage",
        safety_zone="SZ2_EVIDENCE_AND_GATES",
        default_next_safe_action="manual_review_or_targeted_reprocess_plan",
        dry_run_required=False,
        explicit_apply_required=True,
        human_review_required=True,
        execution_boundary="Human triage decides whether a targeted repair, parking decision or explicit override is appropriate.",
        will_not=NO_WRITE_BOUNDARY,
    ),
    "operator_terminal_override": StopRepairStrategy(
        strategy_id="operator_terminal_override",
        label="Terminal-stop operator override",
        safety_zone="SZ2_EVIDENCE_AND_GATES",
        default_next_safe_action="manual_review_terminal_stop",
        dry_run_required=False,
        explicit_apply_required=True,
        human_review_required=True,
        execution_boundary="Automated retries are blocked. Continuation requires an explicit operator override and new evidence.",
        will_not=NO_WRITE_BOUNDARY,
    ),
    "taxonomy_review_required": StopRepairStrategy(
        strategy_id="taxonomy_review_required",
        label="Taxonomy review required",
        safety_zone="SZ2_EVIDENCE_AND_GATES",
        default_next_safe_action="manual_review_terminal_stop",
        dry_run_required=False,
        explicit_apply_required=True,
        human_review_required=True,
        execution_boundary="The stop is not specific enough. Improve classification before broad reprocessing.",
        will_not=NO_WRITE_BOUNDARY,
    ),
}

STOP_TAXONOMY: dict[str, StopTaxonomyEntry] = {
    "not_stop_like": StopTaxonomyEntry(
        category="not_stop_like",
        lifecycle_class="not_stop",
        severity="info",
        terminal=False,
        default_reprocess="not_applicable",
        false_negative_risk="none",
        repair_strategy_id="no_repair_not_stop",
        description="The reviewed gate result is not a stop-like decision.",
        good_stop_when="The pipeline can continue or delegate to the next normal state-machine step.",
        false_negative_risk_when="Not applicable.",
    ),
    "recoverable_url_problem": StopTaxonomyEntry(
        category="recoverable_url_problem",
        lifecycle_class="false_negative_risk_stop",
        severity="review",
        terminal=False,
        default_reprocess="allow_with_recovery",
        false_negative_risk="medium",
        repair_strategy_id="bounded_source_url_recovery",
        description="The URL appears stale, wrong, missing or insufficiently recovered.",
        good_stop_when="The URL clearly points to a dead or irrelevant public source and recovery has already been exhausted.",
        false_negative_risk_when="A relevant employer may still exist behind another public career/job URL.",
    ),
    "technical_reachability_review": StopTaxonomyEntry(
        category="technical_reachability_review",
        lifecycle_class="repairable_stop",
        severity="review",
        terminal=False,
        default_reprocess="allow_with_review",
        false_negative_risk="medium",
        repair_strategy_id="bounded_source_url_recovery",
        description="Reachability failed without confirmed policy/access risk.",
        good_stop_when="The failure is reproducible and no supported public alternative is available.",
        false_negative_risk_when="Temporary HTTP failures, wrong paths or brittle recovery heuristics may hide valid sources.",
    ),
    "terminal_access_risk": StopTaxonomyEntry(
        category="terminal_access_risk",
        lifecycle_class="good_stop",
        severity="terminal",
        terminal=True,
        default_reprocess="block_without_explicit_override",
        false_negative_risk="low",
        repair_strategy_id="operator_terminal_override",
        description="Confirmed access-denied, challenge, bot-defense or policy-risk evidence.",
        good_stop_when="The stop prevents unsafe or disrespectful acquisition behavior.",
        false_negative_risk_when="Only if later evidence shows the marker was a false positive on a public, accessible job page.",
    ),
    "risk_marker_review": StopTaxonomyEntry(
        category="risk_marker_review",
        lifecycle_class="review_stop",
        severity="review",
        terminal=False,
        default_reprocess="allow_with_review",
        false_negative_risk="medium",
        repair_strategy_id="operator_review_triage",
        description="Risk markers exist but are not strong enough for a terminal access-risk stop.",
        good_stop_when="Review confirms the marker reflects a real challenge, access restriction or policy concern.",
        false_negative_risk_when="Generic page text, consent snippets or footer text triggered an over-sensitive risk stop.",
    ),
    "detail_discovery_gap": StopTaxonomyEntry(
        category="detail_discovery_gap",
        lifecycle_class="false_negative_risk_stop",
        severity="review",
        terminal=False,
        default_reprocess="allow_with_detail_discovery",
        false_negative_risk="high",
        repair_strategy_id="bounded_detail_evidence_discovery",
        description="Origin/source evidence may be valid, but concrete job-detail evidence was not found.",
        good_stop_when="A bounded evidence attempt confirms no relevant concrete job detail can be found.",
        false_negative_risk_when="The current finder is too shallow, too narrow, provider-blind or unable to follow the source's structure.",
    ),
    "weak_relevance_evidence": StopTaxonomyEntry(
        category="weak_relevance_evidence",
        lifecycle_class="false_negative_risk_stop",
        severity="review",
        terminal=False,
        default_reprocess="allow_with_relevance_discovery",
        false_negative_risk="high",
        repair_strategy_id="bounded_relevance_evidence_discovery",
        description="The source did not expose enough profile/location/remote evidence yet.",
        good_stop_when="Bounded evidence confirms the source has no relevant target/profile signal.",
        false_negative_risk_when="The Türsteher saw only weak preview text although relevant job details exist deeper in the source.",
    ),
    "manual_review_required": StopTaxonomyEntry(
        category="manual_review_required",
        lifecycle_class="review_stop",
        severity="review",
        terminal=False,
        default_reprocess="allow_with_review",
        false_negative_risk="medium",
        repair_strategy_id="operator_review_triage",
        description="A gate requires review, but no more specific stop taxonomy category matched.",
        good_stop_when="The review boundary prevents uncontrolled continuation across an uncertain state.",
        false_negative_risk_when="The missing specificity hides whether URL, relevance, detail or risk evidence is actually repairable.",
    ),
    "terminal_unclassified": StopTaxonomyEntry(
        category="terminal_unclassified",
        lifecycle_class="taxonomy_gap_stop",
        severity="terminal",
        terminal=True,
        default_reprocess="block_without_explicit_override",
        false_negative_risk="medium",
        repair_strategy_id="taxonomy_review_required",
        description="A gate recorded an abort/failure but no precise recoverable or good-stop category matched.",
        good_stop_when="The abort protects safety while classification is incomplete.",
        false_negative_risk_when="The category is too broad and may bury a repairable false negative.",
    ),
}


def taxonomy_entry_for_category(category: str | None) -> StopTaxonomyEntry:
    """Return the canonical taxonomy entry for a category.

    Unknown categories are intentionally mapped to ``terminal_unclassified`` so
    callers fail closed instead of treating unknown stop labels as repairable.
    """

    key = (category or "").strip() or "terminal_unclassified"
    return STOP_TAXONOMY.get(key, STOP_TAXONOMY["terminal_unclassified"])


def repair_strategy_for_id(strategy_id: str | None) -> StopRepairStrategy:
    key = (strategy_id or "").strip() or "taxonomy_review_required"
    return REPAIR_STRATEGIES.get(key, REPAIR_STRATEGIES["taxonomy_review_required"])


def repair_strategy_for_category(category: str | None) -> StopRepairStrategy:
    entry = taxonomy_entry_for_category(category)
    return repair_strategy_for_id(entry.repair_strategy_id)


def stop_taxonomy_evidence(category: str | None) -> dict[str, Any]:
    """Return taxonomy and strategy evidence fields for reports/gate evidence."""

    entry = taxonomy_entry_for_category(category)
    strategy = repair_strategy_for_id(entry.repair_strategy_id)
    return {
        "stop_category": entry.category,
        "stop_lifecycle_class": entry.lifecycle_class,
        "stop_severity": entry.severity,
        "terminal": entry.terminal,
        "default_reprocess": entry.default_reprocess,
        "false_negative_risk": entry.false_negative_risk,
        "repair_strategy_id": strategy.strategy_id,
        "recommended_next_safe_action": strategy.default_next_safe_action,
        "safety_zone": strategy.safety_zone,
        "human_review_required": strategy.human_review_required,
        "dry_run_required": strategy.dry_run_required,
        "explicit_apply_required": strategy.explicit_apply_required,
    }


def categories_by_lifecycle_class(lifecycle_class: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            entry.category
            for entry in STOP_TAXONOMY.values()
            if entry.lifecycle_class == lifecycle_class
        )
    )


def validate_stop_taxonomy() -> list[str]:
    """Return registry consistency findings; empty means valid."""

    findings: list[str] = []
    for category, entry in sorted(STOP_TAXONOMY.items()):
        if category != entry.category:
            findings.append(f"category key mismatch: {category} != {entry.category}")
        if entry.repair_strategy_id not in REPAIR_STRATEGIES:
            findings.append(f"{category} references missing strategy {entry.repair_strategy_id}")
        if entry.terminal and entry.default_reprocess != "block_without_explicit_override":
            findings.append(f"{category} is terminal but default_reprocess is {entry.default_reprocess!r}")
        if not entry.description.strip():
            findings.append(f"{category} has no description")
    for strategy_id, strategy in sorted(REPAIR_STRATEGIES.items()):
        if strategy_id != strategy.strategy_id:
            findings.append(f"strategy key mismatch: {strategy_id} != {strategy.strategy_id}")
        if not strategy.safety_zone.startswith("SZ"):
            findings.append(f"{strategy_id} has invalid safety zone {strategy.safety_zone!r}")
    return findings


def taxonomy_reference_rows(categories: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Return stable rows for docs, reports and lightweight UI tables."""

    selected = categories or sorted(STOP_TAXONOMY)
    rows: list[dict[str, Any]] = []
    for category in selected:
        entry = taxonomy_entry_for_category(category)
        strategy = repair_strategy_for_id(entry.repair_strategy_id)
        row = entry.as_dict()
        row.update(
            {
                "repair_label": strategy.label,
                "recommended_next_safe_action": strategy.default_next_safe_action,
                "safety_zone": strategy.safety_zone,
                "human_review_required": strategy.human_review_required,
            }
        )
        rows.append(row)
    return rows
