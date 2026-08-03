"""Run a read-only discovery-to-Top-5 golden-path portfolio audit."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_origin_observation_seed_pool_agent import collect_seeds
from src.config import get_database_config
from src.search_intelligence.product_e2e_golden_path import (
    AUDIT_BOUNDARY,
    DiscoveryCase,
    GateState,
    LifecycleSnapshot,
    case_from_seed,
    select_representative_cases,
    stage_status_counts,
    summarize_gaps,
    trace_case,
)

RESULT = "PRODUCT_E2E_GOLDEN_PATH_AUDIT_COMPLETED"


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


class SnapshotRepository:
    def __init__(self, conn: psycopg.Connection[Any]) -> None:
        self.conn = conn
        self._relations = self._load_relations()
        self._columns: dict[str, set[str]] = {}

    def _load_relations(self) -> set[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                UNION
                SELECT table_name
                FROM information_schema.views
                WHERE table_schema = 'public'
                """
            )
            return {str(row["table_name"]) for row in cur.fetchall()}

    def relation_exists(self, name: str) -> bool:
        return name in self._relations

    def columns(self, name: str) -> set[str]:
        if name in self._columns:
            return self._columns[name]
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (name,),
            )
            columns = {str(row["column_name"]) for row in cur.fetchall()}
        self._columns[name] = columns
        return columns

    def _fetchone(
        self,
        query: str,
        params: tuple[object, ...],
    ) -> Mapping[str, object] | None:
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            row = cur.fetchone()
        return None if row is None else dict(row)

    def _fetchall(
        self,
        query: str,
        params: tuple[object, ...],
    ) -> list[Mapping[str, object]]:
        with self.conn.cursor() as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def _candidate_row(self, case: DiscoveryCase) -> Mapping[str, object] | None:
        if not self.relation_exists("gold_candidate_lifecycle_status"):
            return None
        if case.company_key:
            row = self._fetchone(
                """
                SELECT *
                FROM gold_candidate_lifecycle_status
                WHERE company_key = %s
                ORDER BY last_signal_at DESC NULLS LAST, candidate_id DESC
                LIMIT 1
                """,
                (case.company_key,),
            )
            if row is not None:
                return row
        if case.company_name:
            return self._fetchone(
                """
                SELECT *
                FROM gold_candidate_lifecycle_status
                WHERE lower(display_company_name) = lower(%s)
                ORDER BY last_signal_at DESC NULLS LAST, candidate_id DESC
                LIMIT 1
                """,
                (case.company_name,),
            )
        return None

    def _gates(self, candidate_id: int | None) -> dict[str, GateState]:
        if candidate_id is None or not self.relation_exists(
            "employer_origin_candidate_gate_reviews"
        ):
            return {}
        rows = self._fetchall(
            """
            SELECT DISTINCT ON (gate_name)
                gate_name, gate_status, decision, stop_reason
            FROM employer_origin_candidate_gate_reviews
            WHERE candidate_id = %s
            ORDER BY gate_name, updated_at DESC NULLS LAST, id DESC
            """,
            (candidate_id,),
        )
        return {
            str(row["gate_name"]): GateState(
                gate_name=str(row["gate_name"]),
                gate_status=str(row["gate_status"]),
                decision=None if row.get("decision") is None else str(row["decision"]),
                stop_reason=(
                    None if row.get("stop_reason") is None else str(row["stop_reason"])
                ),
            )
            for row in rows
        }

    def _queue_row(self, candidate_id: int | None) -> Mapping[str, object] | None:
        if candidate_id is None or not self.relation_exists(
            "gold_connector_build_candidate_queue"
        ):
            return None
        return self._fetchone(
            """
            SELECT queue_action, queue_reason
            FROM gold_connector_build_candidate_queue
            WHERE candidate_id = %s
            LIMIT 1
            """,
            (candidate_id,),
        )

    def _silver_job_count(self, case: DiscoveryCase) -> int:
        if not self.relation_exists("silver_jobs"):
            return 0
        columns = self.columns("silver_jobs")
        if case.company_key and "normalized_company_name" in columns:
            row = self._fetchone(
                """
                SELECT count(*)::integer AS count
                FROM silver_jobs
                WHERE normalized_company_name = %s
                """,
                (case.company_key,),
            )
            if row and int(row["count"] or 0) > 0:
                return int(row["count"])
        if case.company_name and "company_name" in columns:
            row = self._fetchone(
                """
                SELECT count(*)::integer AS count
                FROM silver_jobs
                WHERE lower(company_name) = lower(%s)
                """,
                (case.company_name,),
            )
            return 0 if row is None else int(row["count"] or 0)
        return 0

    def _exact_raw_job_count(self, case: DiscoveryCase) -> int | None:
        if not case.seed_url or not self.relation_exists("raw_jobs"):
            return None
        if "source_url" not in self.columns("raw_jobs"):
            return None
        row = self._fetchone(
            "SELECT count(*)::integer AS count FROM raw_jobs WHERE source_url = %s",
            (case.seed_url,),
        )
        return None if row is None else int(row["count"] or 0)

    def _readiness_counts(self, case: DiscoveryCase) -> dict[str, int]:
        if not case.company_name or not self.relation_exists(
            "gold_product_v1_job_readiness"
        ):
            return {}
        rows = self._fetchall(
            """
            SELECT product_readiness_status, count(*)::integer AS count
            FROM gold_product_v1_job_readiness
            WHERE lower(company_name) = lower(%s)
            GROUP BY product_readiness_status
            ORDER BY product_readiness_status
            """,
            (case.company_name,),
        )
        return {
            str(row["product_readiness_status"]): int(row["count"]) for row in rows
        }

    def _top5_count(self, case: DiscoveryCase) -> int:
        if not case.company_name or not self.relation_exists("gold_product_v1_top_jobs"):
            return 0
        row = self._fetchone(
            """
            SELECT count(*)::integer AS count
            FROM gold_product_v1_top_jobs
            WHERE lower(company_name) = lower(%s)
            """,
            (case.company_name,),
        )
        return 0 if row is None else int(row["count"] or 0)

    def load_snapshot(self, case: DiscoveryCase) -> LifecycleSnapshot:
        candidate = self._candidate_row(case)
        candidate_id = None if candidate is None else int(candidate["candidate_id"])
        queue = self._queue_row(candidate_id) or {}
        return LifecycleSnapshot(
            candidate_id=candidate_id,
            candidate_status=(
                None if candidate is None else _text(candidate.get("candidate_status"))
            ),
            candidate_url=(
                None if candidate is None else _text(candidate.get("candidate_url"))
            ),
            current_stage=(
                None if candidate is None else _text(candidate.get("current_stage"))
            ),
            blocking_gate=(
                None if candidate is None else _text(candidate.get("blocking_gate"))
            ),
            blocking_gate_status=(
                None
                if candidate is None
                else _text(candidate.get("blocking_gate_status"))
            ),
            blocker_reason=(
                None if candidate is None else _text(candidate.get("blocker_reason"))
            ),
            generation_status=(
                None if candidate is None else _text(candidate.get("generation_status"))
            ),
            build_status=(
                None if candidate is None else _text(candidate.get("build_status"))
            ),
            queue_action=_text(queue.get("queue_action")),
            queue_reason=_text(queue.get("queue_reason")),
            gate_states=self._gates(candidate_id),
            exact_raw_job_count=self._exact_raw_job_count(case),
            silver_job_count=self._silver_job_count(case),
            product_readiness_counts=self._readiness_counts(case),
            top5_job_count=self._top5_count(case),
        )


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _source_counts(cases: Iterable[DiscoveryCase]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        counts[case.discovery_source_class] = counts.get(case.discovery_source_class, 0) + 1
    return dict(sorted(counts.items()))


def build_report(
    cases: list[DiscoveryCase], snapshots: list[LifecycleSnapshot]
) -> dict[str, object]:
    traces = [
        trace_case(case, snapshot)
        for case, snapshot in zip(cases, snapshots, strict=True)
    ]
    gaps = summarize_gaps(traces)
    operator_decisions = [
        {
            "case_id": trace.case.case_id,
            "company_key": trace.case.company_key,
            "stage": stage.stage,
            "decision": stage.operator_decision,
            "reason_code": stage.reason_code,
        }
        for trace in traces
        for stage in trace.stages
        if stage.operator_decision
    ]
    missing_primary_classes = sorted(
        set(
            (
                "aggregator_company_discovery",
                "public_job_api_discovery",
                "manual_observation",
            )
        )
        - {case.discovery_source_class for case in cases}
    )
    return {
        "schema_version": "product_e2e_golden_path_audit.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "boundary": AUDIT_BOUNDARY,
        "selection": {
            "selected_case_count": len(cases),
            "maximum_case_count": 5,
            "source_class_counts": _source_counts(cases),
            "missing_primary_source_classes": missing_primary_classes,
            "company_specific_selection": False,
        },
        "summary": {
            "completed_case_count": sum(
                trace.overall_status == "completed" for trace in traces
            ),
            "operator_decision_case_count": sum(
                trace.overall_status == "operator_decision_required" for trace in traces
            ),
            "blocked_case_count": sum(
                trace.overall_status == "blocked" for trace in traces
            ),
            "operator_decision_count": len(operator_decisions),
            "generic_cross_source_gap_count": sum(
                gap.scope == "generic_cross_source_gap" for gap in gaps
            ),
        },
        "stage_status_counts": stage_status_counts(traces),
        "operator_decisions": operator_decisions,
        "gaps": [asdict(gap) for gap in gaps],
        "cases": [
            {
                "case": asdict(trace.case),
                "snapshot": asdict(snapshot),
                "overall_status": trace.overall_status,
                "next_blocker_stage": trace.next_blocker_stage,
                "stages": [asdict(stage) for stage in trace.stages],
            }
            for trace, snapshot in zip(traces, snapshots, strict=True)
        ],
    }


def render_markdown(report: Mapping[str, object]) -> str:
    selection = report["selection"]
    summary = report["summary"]
    assert isinstance(selection, Mapping)
    assert isinstance(summary, Mapping)
    lines = [
        "# Product E2E Golden-Path Audit",
        "",
        "## Portfolio",
        "",
        (
            f"- selected cases: `{selection['selected_case_count']}` / "
            f"`{selection['maximum_case_count']}`"
        ),
        f"- source classes: `{json.dumps(selection['source_class_counts'], sort_keys=True)}`",
        (
            "- missing primary classes: "
            f"`{json.dumps(selection['missing_primary_source_classes'])}`"
        ),
        "- selection is source-diverse and contains no company allowlist.",
        "",
        "## Outcome",
        "",
        f"- completed cases: `{summary['completed_case_count']}`",
        f"- operator-decision cases: `{summary['operator_decision_case_count']}`",
        f"- blocked cases: `{summary['blocked_case_count']}`",
        f"- cross-source generic gaps: `{summary['generic_cross_source_gap_count']}`",
        "",
        "## Cases",
        "",
    ]
    cases = report["cases"]
    assert isinstance(cases, list)
    for item in cases:
        assert isinstance(item, Mapping)
        case = item["case"]
        assert isinstance(case, Mapping)
        lines.extend(
            [
                f"### {case.get('company_name') or case.get('company_key') or case['case_id']}",
                "",
                f"- discovery class: `{case['discovery_source_class']}`",
                f"- overall status: `{item['overall_status']}`",
                f"- next blocker: `{item['next_blocker_stage'] or '-'}`",
                "",
            ]
        )
        stages = item["stages"]
        assert isinstance(stages, list)
        for stage in stages:
            assert isinstance(stage, Mapping)
            lines.append(
                f"- `{stage['stage']}` → **{stage['status']}**: {stage['reason']}"
            )
        lines.append("")

    lines.extend(["## Generic and local gaps", ""])
    gaps = report["gaps"]
    assert isinstance(gaps, list)
    if not gaps:
        lines.append("- No unresolved gap was observed in the selected portfolio.")
    for gap in gaps:
        assert isinstance(gap, Mapping)
        lines.append(
            "- "
            f"`{gap['stage']}` / `{gap['reason_code']}`: "
            f"{gap['occurrence_count']} case(s), scope `{gap['scope']}`, "
            f"sources `{', '.join(gap['discovery_source_classes'])}`"
        )

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "This audit performs read-only database inspection only. It makes no "
                "external request, writes no pipeline state, builds or activates no "
                "connector, and changes no ranking or application behavior."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_report(
    report: Mapping[str, object], output_dir: Path
) -> tuple[Path, Path]:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / f"product_e2e_golden_path_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    json_path = run_dir / "result.json"
    markdown_path = run_dir / "result.md"
    json_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Trace up to five source-diverse discovery cases through the generic "
            "Product V1 chain."
        )
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--limit-per-seed-source", type=int, default=100)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "product_v1_runtime_artifacts",
    )
    parser.add_argument("--no-write-artifact", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    if args.limit < 1 or args.limit > 5:
        raise SystemExit("--limit must be between 1 and 5")
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        seeds = collect_seeds(conn, limit_per_source=args.limit_per_seed_source)
        cases = select_representative_cases(
            (case_from_seed(seed) for seed in seeds),
            limit=args.limit,
        )
        repository = SnapshotRepository(conn)
        snapshots = [repository.load_snapshot(case) for case in cases]
        conn.rollback()

    report = build_report(cases, snapshots)
    selection = report["selection"]
    summary = report["summary"]
    assert isinstance(selection, Mapping)
    assert isinstance(summary, Mapping)
    print("Product E2E generic discovery-to-Top-5 audit")
    print(f"selected_cases: {selection['selected_case_count']}/5")
    print(
        f"source_classes: {json.dumps(selection['source_class_counts'], sort_keys=True)}"
    )
    print(
        "missing_primary_source_classes: "
        f"{json.dumps(selection['missing_primary_source_classes'])}"
    )
    print(f"completed_cases: {summary['completed_case_count']}")
    print(f"operator_decision_cases: {summary['operator_decision_case_count']}")
    print(f"blocked_cases: {summary['blocked_case_count']}")
    print(f"generic_cross_source_gaps: {summary['generic_cross_source_gap_count']}")
    cases_payload = report["cases"]
    assert isinstance(cases_payload, list)
    for item in cases_payload:
        assert isinstance(item, Mapping)
        case = item["case"]
        assert isinstance(case, Mapping)
        print(
            "case: "
            f"source={case['discovery_source_class']} | "
            f"company={case.get('company_name') or case.get('company_key') or '-'} | "
            f"status={item['overall_status']} | "
            f"blocker={item['next_blocker_stage'] or '-'}"
        )
    if not args.no_write_artifact:
        json_path, markdown_path = write_report(report, args.output_dir)
        print(f"artifact_json: {json_path}")
        print(f"artifact_markdown: {markdown_path}")
    else:
        print("artifact_write: disabled")
    print(f"RESULT: {RESULT}")
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
