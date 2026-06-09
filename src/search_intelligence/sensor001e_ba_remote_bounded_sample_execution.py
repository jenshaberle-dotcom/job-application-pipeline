from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Protocol

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchProfile, SearchTerm
from src.normalization.company_keys import normalize_company_key
from src.search_intelligence.market_sensor_controlled_activation import (
    BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
    BA_SOURCE_NAME,
    MarketSensorProfileState,
    MarketSensorTermState,
)
from src.search_intelligence.market_sensor_sample_run_plan import (
    build_ba_remote_bounded_sample_run_plan,
)

MISSING_DISPLAY_VALUE = "<missing>"


class ExistingRawJobLookup(Protocol):
    def __call__(self, *, source_name: str, external_job_id: str | None) -> bool: ...


@dataclass(frozen=True)
class Sensor001ESampleTermResult:
    search_term: str
    requested_url: str | None
    total_loaded: int
    would_insert_count: int
    duplicate_count: int
    distinct_company_count: int
    new_company_count: int
    known_company_overlap_count: int
    remote_signal_count: int
    local_or_hannover_overlap_count: int
    profile_relevant_title_count: int
    irrelevant_title_count: int
    error_count: int
    companies: tuple[str, ...]
    titles: tuple[str, ...]
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Sensor001ESampleExecutionReport:
    overall_status: str
    source_name: str
    review_profile_name: str
    sample_terms: tuple[str, ...]
    sample_limits: Mapping[str, Any]
    term_results: tuple[Sensor001ESampleTermResult, ...]
    missing_terms: tuple[str, ...]
    safety_boundary: Mapping[str, Any]
    findings: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        total_loaded_by_term = {result.search_term: result.total_loaded for result in self.term_results}
        inserted_count_by_term = {result.search_term: result.would_insert_count for result in self.term_results}
        duplicate_count_by_term = {result.search_term: result.duplicate_count for result in self.term_results}
        return {
            "schema_version": "sensor001e.ba_remote_nationwide_bounded_sample_execution.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "work_item": "SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review",
            "source_name": self.source_name,
            "review_profile_name": self.review_profile_name,
            "overall_status": self.overall_status,
            "sample_terms": list(self.sample_terms),
            "sample_limits": dict(self.sample_limits),
            "term_results": [result.as_dict() for result in self.term_results],
            "metrics": {
                "total_loaded_by_term": total_loaded_by_term,
                "inserted_count_by_term": inserted_count_by_term,
                "duplicate_count_by_term": duplicate_count_by_term,
                "distinct_company_count": sum(result.distinct_company_count for result in self.term_results),
                "new_company_count": sum(result.new_company_count for result in self.term_results),
                "known_company_overlap_count": sum(result.known_company_overlap_count for result in self.term_results),
                "remote_signal_count": sum(result.remote_signal_count for result in self.term_results),
                "local_or_hannover_overlap_count": sum(result.local_or_hannover_overlap_count for result in self.term_results),
                "profile_relevant_title_count": sum(result.profile_relevant_title_count for result in self.term_results),
                "irrelevant_title_count": sum(result.irrelevant_title_count for result in self.term_results),
                "error_count": sum(result.error_count for result in self.term_results),
            },
            "missing_terms": list(self.missing_terms),
            "safety_boundary": dict(self.safety_boundary),
            "findings": list(self.findings),
            "next_action": self.next_action,
        }


def build_sensor001e_bounded_sample_execution(
    *,
    profiles: Iterable[MarketSensorProfileState],
    terms: Iterable[MarketSensorTermState],
    connector: JobSourceConnector,
    existing_raw_job_lookup: ExistingRawJobLookup,
    known_company_keys: Iterable[str] = (),
    max_terms: int = 2,
    execute_approved: bool = False,
) -> Sensor001ESampleExecutionReport:
    profile_tuple = tuple(profiles)
    term_tuple = tuple(terms)
    plan = build_ba_remote_bounded_sample_run_plan(profile_tuple, term_tuple, max_terms=max_terms)
    plan_payload = plan.as_dict()

    sample_terms = tuple(plan_payload.get("sample_terms", []))
    sample_limits = dict(plan_payload.get("sample_limits", {}))
    safety_boundary = {
        "operator_approved_external_sample": bool(execute_approved),
        "external_requests": bool(execute_approved),
        "database_reads": True,
        "database_writes": False,
        "raw_jobs_write": False,
        "ingestion_run_write": False,
        "scheduler_mutation": False,
        "candidate_or_gate_mutation": False,
        "connector_activation": False,
        "bronze_silver_gold_mutation": False,
        "productive_activation": False,
    }

    if plan_payload.get("overall_status") != "sample_plan_ready":
        return Sensor001ESampleExecutionReport(
            overall_status="blocked_until_sample_plan_ready",
            source_name=BA_SOURCE_NAME,
            review_profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            sample_terms=sample_terms,
            sample_limits=sample_limits,
            term_results=(),
            missing_terms=sample_terms,
            safety_boundary=safety_boundary,
            findings=("SENSOR-001D sample plan is not ready; do not execute external sample.",),
            next_action="Repair SENSOR-001D readiness before SENSOR-001E execution.",
        )

    if not execute_approved:
        return Sensor001ESampleExecutionReport(
            overall_status="approval_required",
            source_name=BA_SOURCE_NAME,
            review_profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            sample_terms=sample_terms,
            sample_limits=sample_limits,
            term_results=(),
            missing_terms=sample_terms,
            safety_boundary=safety_boundary,
            findings=("External BA sample was not executed because --execute-approved was not provided.",),
            next_action="Rerun with --execute-approved only after explicit operator approval.",
        )

    review_profile = _single_review_profile(profile_tuple)
    bounded_profile = SearchProfile(
        id=review_profile.id,
        profile_name=review_profile.profile_name,
        source_name=review_profile.source_name,
        search_location=review_profile.search_location,
        search_radius_km=review_profile.search_radius_km,
        offer_type=review_profile.offer_type,
        page_size=int(sample_limits.get("page_size_per_term", review_profile.page_size)),
    )
    known_key_set = {key for key in known_company_keys if key}

    term_results = tuple(
        execute_sample_term(
            connector=connector,
            profile=bounded_profile,
            search_term=term,
            existing_raw_job_lookup=existing_raw_job_lookup,
            known_company_keys=known_key_set,
        )
        for term in sample_terms
    )

    missing_terms = tuple(term for term in sample_terms if term not in {result.search_term for result in term_results})
    error_count = sum(result.error_count for result in term_results)
    overall_status = "sample_executed_with_errors" if error_count else "sample_executed"
    findings = [
        "Executed bounded external BA sample without writing raw_jobs or ingestion_runs.",
        "Profile remains an inactive review profile; scheduler and productive activation remain unchanged.",
    ]
    if error_count:
        findings.append("At least one sampled term failed; inspect term_results before SENSOR-001F decision.")

    return Sensor001ESampleExecutionReport(
        overall_status=overall_status,
        source_name=BA_SOURCE_NAME,
        review_profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
        sample_terms=sample_terms,
        sample_limits=sample_limits,
        term_results=term_results,
        missing_terms=missing_terms,
        safety_boundary=safety_boundary,
        findings=tuple(findings),
        next_action="Run SENSOR-001F result decision using these bounded sample metrics.",
    )


def execute_sample_term(
    *,
    connector: JobSourceConnector,
    profile: SearchProfile,
    search_term: str,
    existing_raw_job_lookup: ExistingRawJobLookup,
    known_company_keys: set[str],
) -> Sensor001ESampleTermResult:
    try:
        records, requested_url = connector.fetch_jobs(profile, SearchTerm(search_term=search_term, id=None))
    except Exception as exc:
        return Sensor001ESampleTermResult(
            search_term=search_term,
            requested_url=None,
            total_loaded=0,
            would_insert_count=0,
            duplicate_count=0,
            distinct_company_count=0,
            new_company_count=0,
            known_company_overlap_count=0,
            remote_signal_count=0,
            local_or_hannover_overlap_count=0,
            profile_relevant_title_count=0,
            irrelevant_title_count=0,
            error_count=1,
            companies=(),
            titles=(),
            error=f"{type(exc).__name__}: {exc}",
        )

    seen_companies: Counter[str] = Counter()
    titles: list[str] = []
    duplicate_count = 0
    remote_signal_count = 0
    local_or_hannover_overlap_count = 0
    profile_relevant_title_count = 0
    irrelevant_title_count = 0

    for record in records:
        company = get_record_display_company(record)
        title = get_record_display_title(record)
        company_key = normalize_company_key(company)
        if company_key:
            seen_companies[company_key] += 1
        if title:
            titles.append(title)
        if existing_raw_job_lookup(source_name=record.source_name, external_job_id=record.external_job_id):
            duplicate_count += 1
        if _has_remote_signal(record):
            remote_signal_count += 1
        if _has_local_or_hannover_signal(record):
            local_or_hannover_overlap_count += 1
        if _is_profile_relevant_title(title):
            profile_relevant_title_count += 1
        else:
            irrelevant_title_count += 1

    distinct_keys = tuple(sorted(seen_companies))
    known_company_overlap_count = sum(1 for key in distinct_keys if key in known_company_keys)
    new_company_count = max(0, len(distinct_keys) - known_company_overlap_count)

    return Sensor001ESampleTermResult(
        search_term=search_term,
        requested_url=requested_url,
        total_loaded=len(records),
        would_insert_count=max(0, len(records) - duplicate_count),
        duplicate_count=duplicate_count,
        distinct_company_count=len(distinct_keys),
        new_company_count=new_company_count,
        known_company_overlap_count=known_company_overlap_count,
        remote_signal_count=remote_signal_count,
        local_or_hannover_overlap_count=local_or_hannover_overlap_count,
        profile_relevant_title_count=profile_relevant_title_count,
        irrelevant_title_count=irrelevant_title_count,
        companies=distinct_keys,
        titles=tuple(titles[:10]),
        error_count=0,
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SENSOR-001E BA Remote/Nationwide Bounded Sample Execution Review",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- source_name: `{report.get('source_name')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        "",
        "## Safety boundary",
        "",
    ]
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Metrics", ""])
    for key, value in report.get("metrics", {}).items():
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Term results", ""])
    term_results = report.get("term_results", [])
    if not term_results:
        lines.append("- none")
    for result in term_results:
        lines.append(
            f"- {result.get('search_term')}: loaded={result.get('total_loaded')}, "
            f"would_insert={result.get('would_insert_count')}, duplicates={result.get('duplicate_count')}, "
            f"distinct_companies={result.get('distinct_company_count')}, errors={result.get('error_count')}"
        )
        if result.get("error"):
            lines.append(f"  - error: `{result.get('error')}`")

    lines.extend(["", "## Findings", ""])
    for finding in report.get("findings", []):
        lines.append(f"- {finding}")

    lines.extend(["", "## Next action", "", str(report.get("next_action", "")), ""])
    return "\n".join(lines)


def get_nested_value(data: dict[str, Any], path: tuple[str, ...]) -> str | None:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if current is None:
        return None
    value = str(current).strip()
    return value or None


def get_record_display_title(record: RawJobRecord) -> str:
    return (
        get_nested_value(record.raw_data, ("result_card", "title"))
        or get_nested_value(record.raw_data, ("job", "titel"))
        or get_nested_value(record.raw_data, ("job", "title"))
        or MISSING_DISPLAY_VALUE
    )


def get_record_display_company(record: RawJobRecord) -> str:
    return (
        get_nested_value(record.raw_data, ("result_card", "company_name"))
        or get_nested_value(record.raw_data, ("job", "arbeitgeber"))
        or get_nested_value(record.raw_data, ("job", "company_name"))
        or get_nested_value(record.raw_data, ("job", "company"))
        or MISSING_DISPLAY_VALUE
    )


def _single_review_profile(profiles: tuple[MarketSensorProfileState, ...]) -> MarketSensorProfileState:
    review_profiles = tuple(
        profile for profile in profiles if profile.profile_name == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME
    )
    if len(review_profiles) != 1:
        raise ValueError("Expected exactly one BA remote/nationwide review profile.")
    return review_profiles[0]


def _has_remote_signal(record: RawJobRecord) -> bool:
    haystack = _record_text(record).lower()
    return any(token in haystack for token in ("remote", "homeoffice", "home office", "mobiles arbeiten"))


def _has_local_or_hannover_signal(record: RawJobRecord) -> bool:
    haystack = _record_text(record).lower()
    return any(token in haystack for token in ("hannover", "hildesheim", "braunschweig", "nordstemmen", "30629"))


def _is_profile_relevant_title(title: str) -> bool:
    normalized = title.lower()
    positive = ("data", "daten", "analytics", "engineer", "entwickler", "platform", "warehouse", "etl", "python", "sql")
    negative = ("pflege", "lager", "verkauf", "fahrer", "koch", "reinigung", "erzieher")
    return any(token in normalized for token in positive) and not any(token in normalized for token in negative)


def _record_text(record: RawJobRecord) -> str:
    parts: list[str] = []
    stack: list[Any] = [record.raw_data]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
        elif value is not None:
            parts.append(str(value))
    return " ".join(parts)
