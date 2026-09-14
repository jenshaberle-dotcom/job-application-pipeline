"""Read-only F4A-Q audit of real job requirement evidence.

The audit samples the current canonical Product cohort by reusable source family,
fetches each exact persisted vacancy URL through the existing bounded public-HTTPS
reader, and compares three truths:

1. persisted Product V1 assessment metadata;
2. the current flat-text assessment extractor replayed on fresh Origin evidence;
3. the existing context-aware deterministic Detail Semantics extractor.

Current Product membership is the only cohort authority used here; this diagnostic
does not activate or admit any source. It never writes Product/database state,
calls a provider/LLM, changes ranking/Top-5/application authority, or emits
Candidate Facts/private candidate evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

if not __package__:  # direct ``python scripts/...`` execution
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from src.config import get_database_config
from src.search_intelligence.detail_semantics_deterministic import (
    deterministic_detail_semantics,
)
from src.search_intelligence.product_v1_assessment_evidence import (
    extract_product_v1_assessment_evidence,
)
from src.search_intelligence.product_v1_downstream_preview import (
    DownstreamPreviewStop,
    fetch_public_https_detail_text,
)


REQUESTED_SEMANTIC_FIELDS = ("seniority", "skills", "remote")


def _source_family(source_name: object) -> str:
    value = str(source_name or "").strip().casefold()
    if not value:
        return "unknown"
    if value.startswith("generic_origin:"):
        return "generic_origin"
    if ":" in value:
        return value.split(":", 1)[0]
    return value


def _canonical_seniority(value: object) -> str:
    text = str(value or "").strip().casefold()
    aliases = {
        "jr.": "junior",
        "jr": "junior",
        "sr.": "senior",
        "sr": "senior",
        "entry level": "junior",
        "berufseinsteiger": "junior",
        "graduate": "junior",
    }
    text = aliases.get(text, text)
    for level in ("principal", "staff", "lead", "senior", "mid", "junior"):
        if level in text:
            return level
    return "unknown"


def _read_rows() -> list[dict[str, object]]:
    sql = """
        SELECT
            current_job.id AS silver_job_id,
            current_job.source_name,
            current_job.source_url,
            current_job.title,
            current_job.company_name,
            current_job.city,
            current_job.country,
            assessment.employment_type,
            assessment.employment_evidence_status,
            assessment.required_languages,
            assessment.language_evidence_status,
            assessment.weekly_hours_min,
            assessment.weekly_hours_max,
            assessment.weekly_hours_evidence_status,
            assessment.work_model,
            assessment.title_seniority,
            assessment.requirements_seniority,
            assessment.seniority_evidence_status,
            assessment.capability_fit_status,
            assessment.updated_at AS assessment_updated_at
        FROM gold_current_job_opportunities current_job
        JOIN job_product_assessments assessment
          ON assessment.silver_job_id = current_job.id
        ORDER BY current_job.source_name, current_job.id
    """
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN READ ONLY")
            cur.execute(sql)
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    return rows


def _sample_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    max_per_family: int,
    max_jobs: int,
) -> list[dict[str, object]]:
    by_family: dict[str, list[dict[str, object]]] = defaultdict(list)
    for raw in rows:
        row = dict(raw)
        by_family[_source_family(row.get("source_name"))].append(row)

    selected: list[dict[str, object]] = []
    # Round-robin by family avoids a large generic-origin family crowding out
    # smaller reusable ATS/source families.
    families = sorted(by_family)
    for index in range(max_per_family):
        for family in families:
            candidates = by_family[family]
            if index >= len(candidates):
                continue
            selected.append(candidates[index])
            if len(selected) >= max_jobs:
                return selected
    return selected


def _audit_row(row: Mapping[str, object]) -> dict[str, object]:
    source_url = str(row.get("source_url") or "").strip()
    final_url, page_title, detail_text = fetch_public_https_detail_text(source_url)
    current = extract_product_v1_assessment_evidence(
        description=detail_text,
        title=str(row.get("title") or page_title or ""),
        source_url=final_url,
    )
    semantics, references = deterministic_detail_semantics(
        html="",
        text=detail_text,
        page_title=page_title,
        detail_url=final_url,
        target_location=str(row.get("city") or ""),
        requested_fields=REQUESTED_SEMANTIC_FIELDS,
    )
    semantic_seniority = _canonical_seniority(semantics.get("seniority"))
    skills = semantics.get("skills")
    skill_values = list(skills) if isinstance(skills, tuple) else []

    persisted = {
        "employment_type": row.get("employment_type"),
        "required_languages": list(row.get("required_languages") or []),
        "weekly_hours_min": row.get("weekly_hours_min"),
        "weekly_hours_max": row.get("weekly_hours_max"),
        "work_model": row.get("work_model"),
        "title_seniority": row.get("title_seniority"),
        "requirements_seniority": row.get("requirements_seniority"),
    }
    replay = {
        "employment_type": current.employment_type,
        "required_languages": list(current.required_languages),
        "weekly_hours_min": current.weekly_hours_min,
        "weekly_hours_max": current.weekly_hours_max,
        "work_model": current.work_model,
        "title_seniority": current.title_seniority,
        "requirements_seniority": current.requirements_seniority,
    }
    changed = sorted(
        key for key in persisted if persisted.get(key) != replay.get(key)
    )
    opportunities: list[str] = []
    if (
        str(row.get("requirements_seniority") or "unknown") == "unknown"
        and semantic_seniority != "unknown"
    ):
        opportunities.append("seniority_context_signal")
    if (
        str(row.get("title_seniority") or "unknown") == "unknown"
        and semantic_seniority != "unknown"
    ):
        opportunities.append("title_seniority_context_signal")
    if skill_values:
        opportunities.append("skills_signal")
    if semantics.get("remote") and str(row.get("work_model") or "unknown") == "unknown":
        opportunities.append("remote_context_signal")

    return {
        "silver_job_id": int(row.get("silver_job_id") or 0),
        "source_name": row.get("source_name"),
        "source_family": _source_family(row.get("source_name")),
        "company_name": row.get("company_name"),
        "title": row.get("title"),
        "source_url": source_url,
        "final_url": final_url,
        "persisted": persisted,
        "fresh_flat_replay": replay,
        "persisted_vs_fresh_changed_fields": changed,
        "semantic_seniority": semantic_seniority,
        "semantic_skill_count": len(skill_values),
        "semantic_skills": skill_values,
        "semantic_remote_signal": semantics.get("remote"),
        "semantic_reference_count": len(references),
        "hardening_opportunities": opportunities,
        "candidate_fact_content_emitted": False,
    }


def build_report(
    rows: Sequence[Mapping[str, object]],
    *,
    max_per_family: int,
    max_jobs: int,
) -> dict[str, object]:
    sample = _sample_rows(
        rows,
        max_per_family=max_per_family,
        max_jobs=max_jobs,
    )
    family_population = Counter(_source_family(row.get("source_name")) for row in rows)

    audited: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for row in sample:
        try:
            audited.append(_audit_row(row))
        except (DownstreamPreviewStop, ValueError) as exc:
            blocked.append(
                {
                    "silver_job_id": int(row.get("silver_job_id") or 0),
                    "source_name": row.get("source_name"),
                    "source_family": _source_family(row.get("source_name")),
                    "reason": str(exc),
                }
            )

    opportunity_counts = Counter(
        item
        for row in audited
        for item in row.get("hardening_opportunities", [])
        if isinstance(item, str)
    )
    changed_counts = Counter(
        field
        for row in audited
        for field in row.get("persisted_vs_fresh_changed_fields", [])
        if isinstance(field, str)
    )
    return {
        "schema": "job_application_pipeline.f4a_requirement_evidence_audit.v1",
        "mode": "read_only",
        "current_assessed_jobs": len(rows),
        "source_family_population": dict(sorted(family_population.items())),
        "sample_requested": len(sample),
        "audited_jobs": len(audited),
        "blocked_jobs": len(blocked),
        "opportunity_counts": dict(sorted(opportunity_counts.items())),
        "fresh_replay_changed_field_counts": dict(sorted(changed_counts.items())),
        "jobs": audited,
        "blocked": blocked,
        "boundaries": {
            "cohort_authority": "current_canonical_product_assessment_membership",
            "source_activation_or_admission": False,
            "database_reads": True,
            "database_writes": False,
            "network_reads": len(sample),
            "provider_or_llm_requests": 0,
            "candidate_fact_reads": False,
            "candidate_fact_content_emitted": False,
            "ranking_or_top5_mutation": False,
            "application_or_submission_mutation": False,
            "raw_html_persisted": False,
        },
    }


def _print_report(report: Mapping[str, object]) -> None:
    print("=== F4A-Q REQUIREMENT EVIDENCE AUDIT ===")
    for key in (
        "current_assessed_jobs",
        "sample_requested",
        "audited_jobs",
        "blocked_jobs",
    ):
        print(f"{key.upper()}={report.get(key)}")
    print(
        "SOURCE_FAMILY_POPULATION="
        + json.dumps(report.get("source_family_population", {}), sort_keys=True)
    )
    print(
        "OPPORTUNITY_COUNTS="
        + json.dumps(report.get("opportunity_counts", {}), sort_keys=True)
    )
    print(
        "FRESH_REPLAY_CHANGED_FIELD_COUNTS="
        + json.dumps(report.get("fresh_replay_changed_field_counts", {}), sort_keys=True)
    )
    for row in report.get("jobs", []):
        if not isinstance(row, Mapping):
            continue
        print(
            "AUDIT_JOB="
            + json.dumps(
                {
                    "silver_job_id": row.get("silver_job_id"),
                    "source_family": row.get("source_family"),
                    "source_name": row.get("source_name"),
                    "title": row.get("title"),
                    "persisted": row.get("persisted"),
                    "fresh_flat_replay": row.get("fresh_flat_replay"),
                    "semantic_seniority": row.get("semantic_seniority"),
                    "semantic_skill_count": row.get("semantic_skill_count"),
                    "semantic_skills": row.get("semantic_skills"),
                    "semantic_remote_signal": row.get("semantic_remote_signal"),
                    "hardening_opportunities": row.get("hardening_opportunities"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    for row in report.get("blocked", []):
        print("AUDIT_BLOCKED=" + json.dumps(row, ensure_ascii=False, sort_keys=True))
    print("DATABASE_WRITES=0")
    print("PROVIDER_REQUESTS=0")
    print("CANDIDATE_FACT_CONTENT_EMITTED=0")
    print("F4A_REQUIREMENT_EVIDENCE_AUDIT=PASS")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-per-family", type=int, default=3)
    parser.add_argument("--max-jobs", type=int, default=24)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.max_per_family < 1 or args.max_jobs < 1:
        raise SystemExit("audit sample limits must be positive")

    report = build_report(
        _read_rows(),
        max_per_family=args.max_per_family,
        max_jobs=args.max_jobs,
    )
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
