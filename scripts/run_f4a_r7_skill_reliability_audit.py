"""Read-only R7 skill-evidence reliability audit for the current review cohort.

The audit reuses the exact generic Origin parser and Silver projection used by
F4A-R3/R4, then measures skill recall by source family. Optional external
observers are scoped to provider-neutral requirement sections and can propose
exact skill spans through the tool-neutral JSON contract. Those spans are
strictly diagnostic and are never written to Bronze, Silver or Product state.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import shlex
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from scripts import run_f4a_r3_silver_requirement_backfill as baseline
from src.config import get_database_config
from src.connectors.generic_job_detail_evidence import (
    extract_generic_job_detail_evidence,
    project_detail_evidence_into_raw_data,
)
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    fetch_public_https_detail_document,
)
from src.search_intelligence.requirement_section_evidence import (
    extract_requirement_section_evidence,
)
from src.silver.external_observer_contract import (
    ExternalObserverError,
    run_external_skill_observer,
)
from src.silver.requirement_evidence_projection import build_silver_requirement_evidence


REPORT_SCHEMA = "job_application_pipeline.f4a_r7_skill_reliability_audit.v2"
_REQUIREMENT_SECTION_MARKERS = (
    "anforderungen",
    "qualifikationen",
    "dein profil",
    "ihr profil",
    "das bringst du mit",
    "was du mitbringst",
    "kenntnisse",
    "kompetenzen",
    "berufserfahrung",
    "requirements",
    "qualifications",
    "your profile",
    "what you bring",
    "skills",
    "experience",
)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _string_list(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [text for item in value if (text := _text(item))]


def _source_host(url: object) -> str:
    return (urlparse(_text(url)).hostname or "unknown").casefold()


def _requirement_surface_signal(text: object) -> bool:
    normalized = _text(text).casefold()
    return bool(normalized) and any(
        marker in normalized for marker in _REQUIREMENT_SECTION_MARKERS
    )


def _skill_field(payload: Mapping[str, Any]) -> tuple[str, list[str]]:
    field = _mapping(_mapping(payload.get("fields")).get("job_skills"))
    return _text(field.get("status")) or "unknown", _string_list(field.get("values"))


def _normalized_skill(value: object) -> str:
    return " ".join(_text(value).casefold().replace("/", " ").split())


def _is_incremental(candidate: str, current: Sequence[str]) -> bool:
    normalized = _normalized_skill(candidate)
    if not normalized:
        return False
    for existing in current:
        known = _normalized_skill(existing)
        if not known:
            continue
        if normalized == known or normalized in known or known in normalized:
            return False
    return True


def _build_row(
    row: Mapping[str, Any],
    *,
    observer_command: Sequence[str] = (),
    observer_name: str = "external_skill_observer",
) -> dict[str, object]:
    source_url = _text(row.get("source_url"))
    if not source_url:
        raise ValueError("Silver source URL missing")

    document = fetch_public_https_detail_document(source_url)
    if not baseline._same_origin(source_url, document.final_url):
        raise ValueError("detail fetch redirected outside exact Origin")

    detail = extract_generic_job_detail_evidence(
        html=document.html,
        url=document.final_url,
        page_title=document.title,
    )
    requirement_sections = extract_requirement_section_evidence(document.html)

    raw_data = project_detail_evidence_into_raw_data(baseline._best_raw_data(row), detail)
    job = raw_data.get("job")
    if not isinstance(job, dict):
        job = {}
        raw_data["job"] = job
    job["source_url"] = source_url
    if not _text(job.get("title")):
        job["title"] = _text(row.get("title"))

    payload = build_silver_requirement_evidence(
        {
            "id": int(row["raw_job_id"]),
            "source_name": row.get("source_name"),
            "source_url": source_url,
            "title": row.get("title"),
            "raw_data": raw_data,
        }
    )
    skill_status, skills = _skill_field(payload)
    structured_skills = _string_list(detail.get("skills"))
    requirement_text = (
        detail.get("requirement_text_excerpt")
        or detail.get("main_text_excerpt")
        or detail.get("visible_text_excerpt")
        or ""
    )
    requirement_signal = bool(requirement_sections.text) or _requirement_surface_signal(
        requirement_text
    )
    observer_text = requirement_sections.text

    external_count = 0
    external_rejected = 0
    incremental: list[str] = []
    observer_error: str | None = None
    if observer_command and _text(observer_text):
        try:
            observed = run_external_skill_observer(
                command=observer_command,
                text=_text(observer_text),
                observer_name=observer_name,
                timeout_seconds=30.0,
            )
            external_count = len(observed.facts)
            external_rejected = observed.rejected_count
            for fact in observed.facts:
                evidence = _text(fact.evidence)
                if (
                    evidence
                    and _is_incremental(evidence, skills)
                    and evidence not in incremental
                ):
                    incremental.append(evidence)
        except ExternalObserverError as exc:
            observer_error = str(exc)

    return {
        "silver_job_id": int(row["silver_job_id"]),
        "source_name": _text(row.get("source_name")) or "unknown",
        "source_host": _source_host(source_url),
        "title": _text(row.get("title")),
        "parser_family": _text(detail.get("parser_family")) or "unclassified",
        "structured_jobposting_found": detail.get("structured_jobposting_found") is True,
        "requirement_surface_present": bool(_text(requirement_text)),
        "requirement_section_signal": requirement_signal,
        "requirement_section_extracted": bool(requirement_sections.text),
        "requirement_section_count": len(requirement_sections.sections),
        "requirement_section_chars": len(requirement_sections.text),
        "requirement_section_truncated": requirement_sections.truncated,
        "structured_skill_count": len(structured_skills),
        "skill_status": skill_status,
        "skill_count": len(skills),
        "skills": skills,
        "skill_recall_risk": bool(requirement_signal and not skills),
        "external_observer_scope": "requirement_sections",
        "external_observer_candidate_count": external_count,
        "external_observer_rejected_count": external_rejected,
        "external_incremental_skill_count": len(incremental),
        "external_incremental_skill_spans": incremental[:24],
        "external_observer_error": observer_error,
    }


def _aggregate(
    rows: Sequence[Mapping[str, object]], key: str
) -> dict[str, dict[str, object]]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[_text(row.get(key)) or "unknown"].append(row)

    result: dict[str, dict[str, object]] = {}
    for name, items in sorted(grouped.items()):
        requirement_rows = sum(
            bool(item.get("requirement_section_signal")) for item in items
        )
        extracted_rows = sum(
            bool(item.get("requirement_section_extracted")) for item in items
        )
        skill_rows = sum(int(item.get("skill_count") or 0) > 0 for item in items)
        risk_rows = sum(bool(item.get("skill_recall_risk")) for item in items)
        incremental_rows = sum(
            int(item.get("external_incremental_skill_count") or 0) > 0
            for item in items
        )
        result[name] = {
            "job_count": len(items),
            "structured_jobposting_count": sum(
                bool(item.get("structured_jobposting_found")) for item in items
            ),
            "requirement_section_signal_count": requirement_rows,
            "requirement_section_extracted_count": extracted_rows,
            "requirement_section_extracted_ratio": (
                extracted_rows / len(items) if items else 0.0
            ),
            "skill_observed_job_count": skill_rows,
            "skill_recall_risk_count": risk_rows,
            "skill_observed_ratio": skill_rows / len(items) if items else 0.0,
            "skill_observed_on_requirement_signal_ratio": (
                (requirement_rows - risk_rows) / requirement_rows
                if requirement_rows
                else 0.0
            ),
            "external_incremental_job_count": incremental_rows,
            "external_incremental_skill_count": sum(
                int(item.get("external_incremental_skill_count") or 0)
                for item in items
            ),
        }
    return result


def build_report(
    rows: Sequence[Mapping[str, Any]],
    *,
    observer_command: Sequence[str] = (),
    observer_name: str = "external_skill_observer",
) -> dict[str, object]:
    observed: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    unavailable: list[dict[str, object]] = []
    for row in rows:
        try:
            observed.append(
                _build_row(
                    row,
                    observer_command=observer_command,
                    observer_name=observer_name,
                )
            )
        except DownstreamPreviewStop as exc:
            reason = str(exc)
            target = {
                "silver_job_id": row.get("silver_job_id"),
                "source_name": row.get("source_name"),
                "source_url": row.get("source_url"),
                "reason": reason,
            }
            if reason in {
                "preview detail returned HTTP 404",
                "preview detail returned HTTP 410",
            }:
                unavailable.append(target)
            else:
                blocked.append(target)
        except ValueError as exc:
            blocked.append(
                {
                    "silver_job_id": row.get("silver_job_id"),
                    "source_name": row.get("source_name"),
                    "source_url": row.get("source_url"),
                    "reason": str(exc),
                }
            )

    statuses = Counter(
        _text(row.get("skill_status")) or "unknown" for row in observed
    )
    risk_rows = [row for row in observed if row["skill_recall_risk"]]
    section_rows = [row for row in observed if row["requirement_section_extracted"]]
    external_incremental = [
        row for row in observed if int(row["external_incremental_skill_count"]) > 0
    ]
    observer_errors = [
        row for row in observed if row.get("external_observer_error")
    ]
    return {
        "schema": REPORT_SCHEMA,
        "mode": "read_only",
        "candidate_count": len(rows),
        "audited_count": len(observed),
        "origin_unavailable_count": len(unavailable),
        "blocked_count": len(blocked),
        "requirement_section_extracted_job_count": len(section_rows),
        "skill_status_counts": dict(sorted(statuses.items())),
        "skill_observed_job_count": sum(
            int(row["skill_count"]) > 0 for row in observed
        ),
        "skill_recall_risk_count": len(risk_rows),
        "external_observer_enabled": bool(observer_command),
        "external_observer_name": observer_name if observer_command else None,
        "external_observer_scope": "requirement_sections",
        "external_incremental_job_count": len(external_incremental),
        "external_incremental_skill_count": sum(
            int(row["external_incremental_skill_count"])
            for row in external_incremental
        ),
        "external_observer_error_count": len(observer_errors),
        "by_source_name": _aggregate(observed, "source_name"),
        "by_source_host": _aggregate(observed, "source_host"),
        "rows": observed,
        "unavailable": unavailable,
        "blocked": blocked,
        "boundaries": {
            "database_writes": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "candidate_fact_reads": 0,
            "fit_authority": 0,
            "ranking_authority": 0,
            "top5_authority": 0,
            "application_authority": 0,
            "external_observer_product_authority": 0,
            "raw_html_persisted": 0,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--observer-command",
        help=(
            "Optional isolated observer command; parsed with shlex and never "
            "required by JAP runtime."
        ),
    )
    parser.add_argument("--observer-name", default="external_skill_observer")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = tuple(shlex.split(args.observer_command)) if args.observer_command else ()

    review_ids = baseline._review_ids()
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        rows = baseline._load_rows(conn, review_ids)
        conn.rollback()

    report = build_report(
        rows,
        observer_command=command,
        observer_name=args.observer_name,
    )
    print(f"F4A_R7_SKILL_AUDIT_CANDIDATES={report['candidate_count']}")
    print(f"F4A_R7_SKILL_AUDIT_AUDITED={report['audited_count']}")
    print(f"F4A_R7_SKILL_AUDIT_BLOCKED={report['blocked_count']}")
    print(f"F4A_R7_SKILL_AUDIT_UNAVAILABLE={report['origin_unavailable_count']}")
    print(
        "F4A_R7_SKILL_AUDIT_REQUIREMENT_SECTIONS="
        f"{report['requirement_section_extracted_job_count']}"
    )
    print(f"F4A_R7_SKILL_AUDIT_OBSERVED={report['skill_observed_job_count']}")
    print(f"F4A_R7_SKILL_AUDIT_RECALL_RISK={report['skill_recall_risk_count']}")
    print(
        "F4A_R7_SKILL_AUDIT_EXTERNAL_INCREMENTAL_JOBS="
        f"{report['external_incremental_job_count']}"
    )
    print(
        "F4A_R7_SKILL_AUDIT_EXTERNAL_INCREMENTAL_SKILLS="
        f"{report['external_incremental_skill_count']}"
    )
    print(
        "F4A_R7_SKILL_AUDIT_BY_SOURCE="
        + json.dumps(
            report["by_source_name"], ensure_ascii=False, sort_keys=True
        )
    )
    print("F4A_R7_SKILL_AUDIT=PASS")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                report,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
