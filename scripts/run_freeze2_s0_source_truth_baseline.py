"""Freeze-II S0 read-only source-truth baseline.

This runner composes already-qualified acquisition and metadata audits into one
current baseline. It deliberately does not convert diagnostic recipe readiness
into Product connector coverage and never mutates source, Bronze, Silver,
assessment, ranking, application, or Product state.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence

from scripts import product_v1_control_center_base


SCHEMA = "job_application_pipeline.freeze2_s0_source_truth_baseline.v1"
ISSUE = 1038

_CHILDREN = {
    "connector": "scripts.run_deterministic_connector_builder_layer_audit_v6",
    "metadata": "scripts.run_f4a_r3_bronze2e_requirement_audit",
    "skills": "scripts.run_f4a_r7_skill_reliability_audit",
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _source_family(source_name: object) -> str:
    return str(source_name or "").split(":", 1)[0] or "unknown"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def _run_child(module: str, output: Path, extra: Sequence[str] = ()) -> None:
    command = [
        sys.executable,
        "-m",
        module,
        "--output",
        str(output),
        *extra,
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(
            f"S0 child audit failed module={module} exit={completed.returncode}"
        )
    if not output.is_file():
        raise RuntimeError(f"S0 child audit did not write output: {module}")


def _require_zero(value: object, *, field: str) -> None:
    if value not in (0, False, None):
        raise RuntimeError(f"S0 read-only boundary violated: {field}={value!r}")


def _assert_read_only_boundaries(
    connector: Mapping[str, Any],
    metadata: Mapping[str, Any],
    skills: Mapping[str, Any],
) -> None:
    connector_boundary = _mapping(connector.get("boundary"))
    for field in (
        "database_writes",
        "candidate_url_writes",
        "connector_materialization",
        "connector_registration",
        "source_activation",
        "bronze_write",
        "silver_write",
        "product_write",
        "application_action",
        "provider_requests",
        "llm_requests",
        "tavily_requests",
    ):
        _require_zero(connector_boundary.get(field), field=f"connector.{field}")

    metadata_boundary = _mapping(metadata.get("boundaries"))
    for field in (
        "database_writes",
        "provider_calls",
        "candidate_fact_reads",
        "ranking_authority",
        "top5_authority",
        "application_authority",
        "raw_html_persisted",
    ):
        _require_zero(metadata_boundary.get(field), field=f"metadata.{field}")

    skill_boundary = _mapping(skills.get("boundaries"))
    for field in (
        "database_writes",
        "bronze_writes",
        "silver_writes",
        "candidate_fact_reads",
        "fit_authority",
        "ranking_authority",
        "top5_authority",
        "application_authority",
        "external_observer_product_authority",
        "raw_html_persisted",
    ):
        _require_zero(skill_boundary.get(field), field=f"skills.{field}")


def _active_origin_family_counts(
    overview: Mapping[str, Any],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for source in _list(overview.get("sources")):
        if not isinstance(source, Mapping):
            continue
        if str(source.get("source_role") or "") != "employer_origin":
            continue
        activation = _mapping(source.get("activation"))
        if activation.get("active") is not True:
            continue
        counts[_source_family(source.get("source_name"))] += 1
    return dict(sorted(counts.items()))


def _product_family_counts(metadata: Mapping[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in _list(metadata.get("rows")):
        if isinstance(row, Mapping):
            counts[str(row.get("source_family") or "unknown")] += 1
    return dict(sorted(counts.items()))


def build_summary(
    *,
    overview: Mapping[str, Any],
    connector: Mapping[str, Any],
    metadata: Mapping[str, Any],
    skills: Mapping[str, Any],
) -> dict[str, Any]:
    _assert_read_only_boundaries(connector, metadata, skills)

    connector_comparison = _mapping(connector.get("comparison"))
    connector_v6 = _mapping(connector_comparison.get("v6_summary"))
    overview_summary = dict(_mapping(overview.get("summary")))

    first_failures = dict(_mapping(connector_v6.get("first_failure_counts")))
    active_family_counts = _active_origin_family_counts(overview)
    product_family_counts = _product_family_counts(metadata)

    source_family_concentration = {
        "active_employer_origin_by_family": active_family_counts,
        "product_review_jobs_by_family": product_family_counts,
        "active_employer_origin_family_count": len(active_family_counts),
        "product_review_family_count": len(product_family_counts),
    }

    return {
        "schema": SCHEMA,
        "campaign_issue": ISSUE,
        "mode": "read_only",
        "authority": {
            "diagnostic_recipe_ready_is_product_coverage": False,
            "historical_36_of_65_is_current_authority": False,
            "source_activation_authority": False,
            "connector_registration_authority": False,
            "bronze_write_authority": False,
            "silver_write_authority": False,
            "product_write_authority": False,
            "fit_authority": False,
            "ranking_authority": False,
            "application_authority": False,
        },
        "source_overview": {
            "summary": overview_summary,
            "family_concentration": source_family_concentration,
        },
        "connector_builder_diagnostic": {
            "candidate_count": int(connector_v6.get("candidate_count") or 0),
            "diagnostic_recipe_ready_count": int(
                connector_v6.get("recipe_ready_count") or 0
            ),
            "diagnostic_recipe_ready_rate": float(
                connector_v6.get("recipe_ready_rate") or 0.0
            ),
            "first_failure_counts": first_failures,
            "public_feed_attempted_count": int(
                connector_comparison.get("public_feed_attempted_count") or 0
            ),
            "public_feed_promoted_count": int(
                connector_comparison.get("public_feed_promoted_count") or 0
            ),
            "note": (
                "recipe_ready is diagnostic only; strict Product connector coverage "
                "still requires materialized unchanged E2E proof"
            ),
        },
        "metadata_integrity": {
            "candidate_count": int(metadata.get("candidate_count") or 0),
            "operator_candidate_count": int(
                metadata.get("operator_candidate_count") or 0
            ),
            "reachable_count": int(metadata.get("reachable_count") or 0),
            "origin_unavailable_count": int(
                metadata.get("origin_unavailable_count") or 0
            ),
            "reachable_without_extractor_gap_ratio": float(
                metadata.get("reachable_without_extractor_gap_ratio") or 0.0
            ),
            "rows_with_extractor_gap": int(
                metadata.get("rows_with_extractor_gap") or 0
            ),
            "rows_with_projection_loss": int(
                metadata.get("rows_with_silver_to_operator_projection_loss") or 0
            ),
            "violating_row_count": int(metadata.get("violating_row_count") or 0),
            "field_status_counts": dict(
                _mapping(metadata.get("field_status_counts"))
            ),
            "context_observed_counts": dict(
                _mapping(metadata.get("context_observed_counts"))
            ),
            "extractor_gap_source_family_counts": dict(
                _mapping(metadata.get("extractor_gap_source_family_counts"))
            ),
            "coverage_gate_pass": metadata.get("coverage_gate_pass") is True,
        },
        "skill_requirement_reliability": {
            "candidate_count": int(skills.get("candidate_count") or 0),
            "audited_count": int(skills.get("audited_count") or 0),
            "origin_unavailable_count": int(
                skills.get("origin_unavailable_count") or 0
            ),
            "blocked_count": int(skills.get("blocked_count") or 0),
            "requirement_section_extracted_job_count": int(
                skills.get("requirement_section_extracted_job_count") or 0
            ),
            "skill_observed_job_count": int(
                skills.get("skill_observed_job_count") or 0
            ),
            "skill_recall_risk_count": int(
                skills.get("skill_recall_risk_count") or 0
            ),
            "external_observer_enabled": skills.get("external_observer_enabled")
            is True,
            "by_source_name": dict(_mapping(skills.get("by_source_name"))),
        },
        "next_selection_inputs": {
            "connector_first_failures": first_failures,
            "metadata_gap_families": dict(
                _mapping(metadata.get("extractor_gap_source_family_counts"))
            ),
            "skill_recall_by_source": dict(
                _mapping(skills.get("by_source_name"))
            ),
        },
        "boundaries": {
            "database_writes": 0,
            "source_activation": 0,
            "connector_registration": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "product_writes": 0,
            "provider_calls": 0,
            "llm_calls": 0,
            "fit_authority": 0,
            "ranking_authority": 0,
            "application_authority": 0,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/jap-freeze2-s0"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--skip-live-skill-audit",
        action="store_true",
        help=(
            "Use only the DB-backed connector + metadata baseline. This exists for "
            "offline contract tests; the real S0 campaign run must include the live "
            "skill/requirement audit."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    connector_path = output_dir / "connector-builder-v6.json"
    metadata_path = output_dir / "bronze-silver-operator-metadata.json"
    skills_path = output_dir / "skill-requirement-reliability.json"

    overview = product_v1_control_center_base.load_source_connector_overview_payload()

    _run_child(_CHILDREN["connector"], connector_path)
    _run_child(_CHILDREN["metadata"], metadata_path)
    if args.skip_live_skill_audit:
        skills: dict[str, Any] = {
            "candidate_count": 0,
            "audited_count": 0,
            "origin_unavailable_count": 0,
            "blocked_count": 0,
            "requirement_section_extracted_job_count": 0,
            "skill_observed_job_count": 0,
            "skill_recall_risk_count": 0,
            "external_observer_enabled": False,
            "by_source_name": {},
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
    else:
        _run_child(_CHILDREN["skills"], skills_path)
        skills = _read_json(skills_path)

    report = build_summary(
        overview=overview,
        connector=_read_json(connector_path),
        metadata=_read_json(metadata_path),
        skills=skills,
    )

    output = (args.output or (output_dir / "freeze2-s0-summary.json")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    source_summary = _mapping(report["source_overview"]).get("summary")
    connector_summary = _mapping(report["connector_builder_diagnostic"])
    metadata_summary = _mapping(report["metadata_integrity"])
    skill_summary = _mapping(report["skill_requirement_reliability"])

    print("============================================")
    print("FREEZE-II S0 SOURCE TRUTH BASELINE")
    print("============================================")
    print(
        "S0_SOURCE_SUMMARY="
        + json.dumps(source_summary, ensure_ascii=False, sort_keys=True, default=str)
    )
    print(
        "S0_ACTIVE_ORIGIN_FAMILIES="
        + json.dumps(
            _mapping(report["source_overview"])
            .get("family_concentration", {})
            .get("active_employer_origin_by_family", {}),
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    print(
        "S0_CONNECTOR_CANDIDATES="
        + str(connector_summary.get("candidate_count", 0))
    )
    print(
        "S0_DIAGNOSTIC_RECIPE_READY="
        + str(connector_summary.get("diagnostic_recipe_ready_count", 0))
    )
    print(
        "S0_FIRST_FAILURES="
        + json.dumps(
            connector_summary.get("first_failure_counts", {}),
            sort_keys=True,
        )
    )
    print(
        "S0_METADATA_REACHABLE="
        + str(metadata_summary.get("reachable_count", 0))
    )
    print(
        "S0_METADATA_EXTRACTOR_GAP_ROWS="
        + str(metadata_summary.get("rows_with_extractor_gap", 0))
    )
    print(
        "S0_METADATA_PROJECTION_LOSS_ROWS="
        + str(metadata_summary.get("rows_with_projection_loss", 0))
    )
    print(
        "S0_SKILL_OBSERVED="
        + str(skill_summary.get("skill_observed_job_count", 0))
    )
    print(
        "S0_SKILL_RECALL_RISK="
        + str(skill_summary.get("skill_recall_risk_count", 0))
    )
    print("S0_DATABASE_WRITES=0")
    print("S0_SOURCE_ACTIVATION=0")
    print("S0_CONNECTOR_REGISTRATION=0")
    print("S0_FIT_AUTHORITY=0")
    print("S0_RANKING_AUTHORITY=0")
    print(f"S0_REPORT={output}")
    print("FREEZE2_S0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
