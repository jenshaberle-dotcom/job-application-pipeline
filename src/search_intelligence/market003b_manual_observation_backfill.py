"""MARKET-003B manual observation backfill and legacy normalization.

This module converts the manually reconstructed LinkedIn / market reality-check
company list into explicit MARKET-003 learning signals. It is intentionally
code-backed and dry-run-first: exports or spreadsheets are not accepted as hidden
pipeline inputs. Persistence is limited to `market_evidence`, and legacy manual
HDI sightings are normalized without creating jobs, candidates, gates or sources.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.market003_external_market_observations import (
    ManualMarketObservationInput,
    ManualMarketObservationPlan,
    build_manual_market_observation_plan,
    market003_safety_boundary,
)

DEFAULT_BACKFILL_TITLE = "Data Engineer"
DEFAULT_BACKFILL_SEARCH_TERM = "Data Engineer"
DEFAULT_BACKFILL_SOURCE_SEEN_AT = "2026-06-10T00:00:00+00:00"
DEFAULT_BACKFILL_NOTE = (
    "Backfilled from the 2026-06-09/10 manual LinkedIn reality-check company extraction. "
    "Learning signal only; individual relevance is not gate truth."
)


@dataclass(frozen=True)
class ManualObservationBackfillSeed:
    """One code-backed manual company observation seed."""

    company_name: str
    title: str = DEFAULT_BACKFILL_TITLE
    observation_channel: str = "linkedin"
    search_term: str = DEFAULT_BACKFILL_SEARCH_TERM
    observed_at: str = DEFAULT_BACKFILL_SOURCE_SEEN_AT
    location: str | None = None
    remote_signal: str = "unknown"
    relevance_signal: str = "unknown"
    note: str = DEFAULT_BACKFILL_NOTE
    recorded_by: str = "jens"

    @property
    def company_key(self) -> str:
        return normalize_company_key(self.company_name)

    def as_observation_input(self) -> ManualMarketObservationInput:
        return ManualMarketObservationInput(
            company_name=self.company_name,
            title=self.title,
            observation_channel=self.observation_channel,
            observation_source="manual_market_observation_backfill",
            search_term=self.search_term,
            observed_at=self.observed_at,
            location=self.location,
            remote_signal=self.remote_signal,
            relevance_signal=self.relevance_signal,
            note=self.note,
            recorded_by=self.recorded_by,
        )


@dataclass(frozen=True)
class ManualObservationBackfillItem:
    """Review item for one backfill seed."""

    company_name: str
    company_key: str
    title: str
    action: str
    reason: str
    insert_allowed: bool
    existing_market_evidence_ids: tuple[int, ...] = ()
    legacy_market_evidence_ids: tuple[int, ...] = ()
    written_market_evidence_id: int | None = None
    plan: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "company_name": self.company_name,
            "company_key": self.company_key,
            "title": self.title,
            "action": self.action,
            "reason": self.reason,
            "insert_allowed": self.insert_allowed,
            "existing_market_evidence_ids": list(self.existing_market_evidence_ids),
            "legacy_market_evidence_ids": list(self.legacy_market_evidence_ids),
            "written_market_evidence_id": self.written_market_evidence_id,
            "plan": dict(self.plan or {}),
        }


@dataclass(frozen=True)
class LegacyManualEvidenceItem:
    """Legacy manual evidence row requiring MARKET-003 normalization."""

    id: int
    company_name: str
    company_key: str
    title: str
    evidence_kind: str
    input_mode: str | None
    action: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManualObservationBackfillReport:
    """Full MARKET-003B dry-run/write report."""

    write: bool
    seeds_total: int
    insert_planned_count: int
    inserted_count: int
    existing_skip_count: int
    legacy_cover_skip_count: int
    rejected_count: int
    legacy_rows_found: int
    legacy_rows_migrated: int
    items: Sequence[ManualObservationBackfillItem]
    legacy_items: Sequence[LegacyManualEvidenceItem]
    safety_boundary: Mapping[str, bool]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "market003b.manual_observation_backfill.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "work_item": "MARKET-003B Manual Observation Backfill",
            "write": self.write,
            "summary": {
                "seeds_total": self.seeds_total,
                "insert_planned_count": self.insert_planned_count,
                "inserted_count": self.inserted_count,
                "existing_skip_count": self.existing_skip_count,
                "legacy_cover_skip_count": self.legacy_cover_skip_count,
                "rejected_count": self.rejected_count,
                "legacy_rows_found": self.legacy_rows_found,
                "legacy_rows_migrated": self.legacy_rows_migrated,
            },
            "safety_boundary": dict(self.safety_boundary),
            "legacy_items": [item.as_dict() for item in self.legacy_items],
            "items": [item.as_dict() for item in self.items],
            "next_action": suggest_next_market003b_action(self),
        }


DEFAULT_MANUAL_OBSERVATION_BACKFILL_SEEDS: tuple[ManualObservationBackfillSeed, ...] = tuple(
    ManualObservationBackfillSeed(company_name=name)
    for name in (
        "accantec group/x1F",
        "adesso SE",
        "Aignostics",
        "Aptean",
        "Aroundhome",
        "BairesDev LLC",
        "BAUMLINK",
        "Bending Spoons",
        "Braintrust",
        "Clarios",
        "Computer Futures",
        "Concentrix",
        "Concordia Versicherungen",
        "Continental",
        "ConVista Consulting AG",
        "Dataciders GmbH",
        "Deloitte",
        "Dirk Rossmann GmbH",
        "EDEDGE Groups",
        "EEW Energy from Waste GmbH",
        "Enpal",
        "enercity",
        "EY",
        "Fraunhofer IWES",
        "GETEC ENERGIE",
        "Grafana Labs",
        "Harvey Nash",
        "HDI Group",
        "High-Ticket-Matcher",
        "Hyra",
        "ISR Information Products AG",
        "ivv GmbH",
        "Jobgether",
        "Klar",
        "KPMG Deutschland",
        "Land Niedersachsen",
        "Mandl Executives & Experts",
        "Medizinischer Dienst Niedersachsen",
        "mylantech GmbH",
        "NeoBIM GmbH",
        "NETGO GmbH",
        "Nexavi Solutions",
        "OESL-Automotive",
        "OKAPI:Orbits",
        "Oviva",
        "Philips",
        "PRACYVA",
        "Prop Firm Match",
        "Reos GmbH",
        "salesHAX Consulting GmbH",
        "Scalian Germany AG",
        "SPARETECH",
        "Stripe",
        "SVA System Vertrieb Alexander GmbH",
        "TD SYNNEX",
        "Thinkport GmbH",
        "UMATR",
        "evoila",
        "VHV Gruppe",
        "E.ON Grid Solutions",
        "NEW YORKER",
        "Bahlsen GmbH",
        "MEDIFOX DAN",
        "goetel",
        "Atos",
        "Sopra Steria",
        "QUNIS",
        "VALUE AG",
    )
)


def market003b_safety_boundary() -> dict[str, bool]:
    boundary = market003_safety_boundary()
    boundary.update(
        {
            "work_item_market003b_backfill": True,
            "code_backed_backfill_inventory": True,
            "dry_run_by_default": True,
            "database_write_requires_explicit_write_flag": True,
            "database_write_scope_market_evidence_only": True,
            "legacy_manual_evidence_update_scope_market_evidence_only": True,
            "delete_or_destructive_cleanup": False,
            "csv_or_export_as_pipeline_input": False,
            "candidate_creation": False,
            "gate_decision": False,
            "connector_build_or_registration": False,
        }
    )
    return boundary


def build_market003b_report(
    *,
    seeds: Sequence[ManualObservationBackfillSeed],
    existing_manual_rows: Sequence[Mapping[str, Any]],
    legacy_rows: Sequence[Mapping[str, Any]],
    write: bool = False,
    written_ids_by_company_key: Mapping[str, int | None] | None = None,
    migrated_legacy_ids: Iterable[int] = (),
) -> ManualObservationBackfillReport:
    written_ids_by_company_key = written_ids_by_company_key or {}
    migrated_set = {int(row_id) for row_id in migrated_legacy_ids}
    # MARKET-003B is a company-level backfill: a legacy/manual row for the
    # same company already covers the inventory seed even when the legacy title
    # differs (for example HDI's legacy "Data & Analytics Engineer" row vs.
    # the generic backfill title "Data Engineer"). Do not use title-level
    # matching here, otherwise the backfill creates duplicate company evidence
    # while also migrating legacy rows.
    existing_by_company_key = _index_existing_manual_rows(existing_manual_rows)
    legacy_by_company_key = _index_legacy_rows(legacy_rows)
    legacy_items = [_legacy_item_from_row(row, migrated_set=migrated_set, write=write) for row in legacy_rows]

    items: list[ManualObservationBackfillItem] = []
    for seed in seeds:
        plan = build_manual_market_observation_plan(seed.as_observation_input())
        existing_ids = tuple(existing_by_company_key.get(plan.company_key, ()))
        legacy_ids = tuple(legacy_by_company_key.get(plan.company_key, ()))
        item = _build_item(plan, existing_ids=existing_ids, legacy_ids=legacy_ids)
        if write and item.action == "insert_manual_market_observation":
            item = ManualObservationBackfillItem(
                company_name=item.company_name,
                company_key=item.company_key,
                title=item.title,
                action=item.action,
                reason=item.reason,
                insert_allowed=item.insert_allowed,
                existing_market_evidence_ids=item.existing_market_evidence_ids,
                legacy_market_evidence_ids=item.legacy_market_evidence_ids,
                written_market_evidence_id=written_ids_by_company_key.get(item.company_key),
                plan=item.plan,
            )
        items.append(item)

    insert_planned = [item for item in items if item.action == "insert_manual_market_observation"]
    inserted_count = sum(1 for item in insert_planned if item.written_market_evidence_id is not None)
    return ManualObservationBackfillReport(
        write=write,
        seeds_total=len(seeds),
        insert_planned_count=len(insert_planned),
        inserted_count=inserted_count,
        existing_skip_count=sum(1 for item in items if item.action == "skip_existing_manual_market_observation"),
        legacy_cover_skip_count=sum(1 for item in items if item.action == "skip_covered_by_legacy_manual_evidence_migration"),
        rejected_count=sum(1 for item in items if item.action.startswith("reject_")),
        legacy_rows_found=len(legacy_rows),
        legacy_rows_migrated=len(migrated_set),
        items=items,
        legacy_items=legacy_items,
        safety_boundary=market003b_safety_boundary(),
    )


def seeds_to_insert(
    seeds: Sequence[ManualObservationBackfillSeed],
    *,
    existing_manual_rows: Sequence[Mapping[str, Any]],
    legacy_rows: Sequence[Mapping[str, Any]],
) -> list[ManualMarketObservationPlan]:
    report = build_market003b_report(seeds=seeds, existing_manual_rows=existing_manual_rows, legacy_rows=legacy_rows)
    plans: list[ManualMarketObservationPlan] = []
    for item in report.items:
        if item.action == "insert_manual_market_observation" and item.plan is not None:
            seed = next(seed for seed in seeds if seed.company_key == item.company_key)
            plans.append(build_manual_market_observation_plan(seed.as_observation_input()))
    return plans


def suggest_next_market003b_action(report: ManualObservationBackfillReport) -> str:
    if not report.write:
        return "review_market003b_backfill_report_then_rerun_with_write_if_expected"
    if report.insert_planned_count != report.inserted_count:
        return "review_duplicates_or_conflicts_before_interpreting_manual_recall_coverage"
    if report.legacy_rows_found != report.legacy_rows_migrated:
        return "review_legacy_manual_evidence_rows_that_were_not_migrated"
    return "run_market003_review_and_quality001_after_manual_backfill"


def render_market003b_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# MARKET-003B Manual Observation Backfill",
        "",
        f"- schema_version: `{report.get('schema_version')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        f"- work_item: `{report.get('work_item')}`",
        f"- write: `{report.get('write')}`",
        "",
        "## Summary",
        "",
    ]
    for key in (
        "seeds_total",
        "insert_planned_count",
        "inserted_count",
        "existing_skip_count",
        "legacy_cover_skip_count",
        "rejected_count",
        "legacy_rows_found",
        "legacy_rows_migrated",
    ):
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Safety boundary", ""])
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Backfill items", ""])
    for item in report.get("items", []):
        lines.append(
            f"- `{item.get('action')}` | {item.get('company_name')} | "
            f"company_key=`{item.get('company_key')}` | written_id=`{item.get('written_market_evidence_id')}`"
        )
    lines.extend(["", "## Legacy items", ""])
    for item in report.get("legacy_items", []):
        lines.append(
            f"- `{item.get('action')}` | id=`{item.get('id')}` | {item.get('company_name')} | "
            f"kind=`{item.get('evidence_kind')}` | input_mode=`{item.get('input_mode')}`"
        )
    lines.extend(["", "## Next action", "", str(report.get("next_action", "")), ""])
    return "\n".join(lines)


def _build_item(
    plan: ManualMarketObservationPlan,
    *,
    existing_ids: tuple[int, ...],
    legacy_ids: tuple[int, ...],
) -> ManualObservationBackfillItem:
    if not plan.insert_allowed:
        return ManualObservationBackfillItem(
            company_name=plan.company_name,
            company_key=plan.company_key,
            title=plan.title,
            action="reject_incomplete_manual_observation",
            reason=plan.reason,
            insert_allowed=False,
            plan=plan.as_dict(),
        )
    if existing_ids:
        return ManualObservationBackfillItem(
            company_name=plan.company_name,
            company_key=plan.company_key,
            title=plan.title,
            action="skip_existing_manual_market_observation",
            reason="matching MARKET-003 manual observation already exists",
            insert_allowed=False,
            existing_market_evidence_ids=existing_ids,
            plan=plan.as_dict(),
        )
    if legacy_ids:
        return ManualObservationBackfillItem(
            company_name=plan.company_name,
            company_key=plan.company_key,
            title=plan.title,
            action="skip_covered_by_legacy_manual_evidence_migration",
            reason="legacy manual evidence row will be normalized instead of inserting a duplicate",
            insert_allowed=False,
            legacy_market_evidence_ids=legacy_ids,
            plan=plan.as_dict(),
        )
    return ManualObservationBackfillItem(
        company_name=plan.company_name,
        company_key=plan.company_key,
        title=plan.title,
        action="insert_manual_market_observation",
        reason="company from manual reality-check list is not yet present as MARKET-003 evidence",
        insert_allowed=True,
        plan=plan.as_dict(),
    )


def _legacy_item_from_row(row: Mapping[str, Any], *, migrated_set: set[int], write: bool) -> LegacyManualEvidenceItem:
    row_id = int(row["id"])
    action = "migrate_legacy_manual_evidence" if not write else "legacy_manual_evidence_migrated"
    if write and row_id not in migrated_set:
        action = "legacy_manual_evidence_not_migrated"
    return LegacyManualEvidenceItem(
        id=row_id,
        company_name=str(row.get("company_name") or ""),
        company_key=str(row.get("normalized_company_key") or row.get("company_key") or ""),
        title=str(row.get("title") or ""),
        evidence_kind=str(row.get("evidence_kind") or ""),
        input_mode=row.get("input_mode"),
        action=action,
        reason="legacy manual evidence should use MARKET-003 manual observation provenance",
    )


def _index_existing_manual_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[int, ...]]:
    return _index_rows_by_company_key_variants(rows)


def _index_legacy_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[int, ...]]:
    return _index_rows_by_company_key_variants(rows)


def _index_rows_by_company_key_variants(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[int, ...]]:
    index: dict[str, list[int]] = {}
    for row in rows:
        keys = {str(row.get("normalized_company_key") or row.get("company_key") or "").strip()}
        company_name = str(row.get("company_name") or "").strip()
        if company_name:
            keys.add(normalize_company_key(company_name))
        for company_key in keys:
            company_key = company_key.strip()
            if company_key:
                index.setdefault(company_key, []).append(int(row["id"]))
    return {key: tuple(sorted(set(value))) for key, value in index.items()}
