"""Run the Search Intelligence Control Center with Agent Monitor v1 truth.

The retained runtime implementation remains unchanged in the adjacent private
module. This adapter adds read-only gate-event and complete orchestrator-run
signals, then installs the dedicated Agent Monitor v1 ReadModel. It adds no
write route, provider call, activation, ingestion or scheduler mutation.
"""
from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from scripts import _search_intelligence_control_center_runtime as _runtime
from src.search_intelligence.control_center.agent_health_read_model import (
    GateSignalCollection,
    OrchestratorSignalCollection,
    install_agent_health_read_model,
)


install_agent_health_read_model()


def _relation_map(
    conn: psycopg.Connection[Any], names: tuple[str, ...]
) -> dict[str, bool]:
    return {name: _runtime._db_object_exists(conn, name) for name in names}


def _candidate_projection(relations: dict[str, bool]) -> tuple[str, str]:
    if relations.get("gold_candidate_lifecycle_status"):
        join = (
            "left join gold_candidate_lifecycle_status l "
            "on l.candidate_id = c.id"
        )
        fields = """
            coalesce(l.company_key, c.company_key, '') as company_key,
            coalesce(l.display_company_name, c.company_name, c.company_key, '')
                as company_name,
            coalesce(l.source_name_candidate, c.source_name_candidate, '')
                as source_name_candidate
        """
        return join, fields
    return (
        "",
        """
            coalesce(c.company_key, '') as company_key,
            coalesce(c.company_name, c.company_key, '') as company_name,
            coalesce(c.source_name_candidate, '') as source_name_candidate
        """,
    )


def load_agent_gate_reviews() -> GateSignalCollection:
    relation_names = (
        "employer_origin_candidate_gate_reviews",
        "employer_origin_candidate_gate_events",
        "employer_origin_source_candidates",
        "gold_candidate_lifecycle_status",
    )
    with psycopg.connect(
        _runtime.DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        relations = _relation_map(conn, relation_names)
        review_rows: list[object] = []
        event_rows: list[dict[str, object]] = []
        candidate_join, candidate_fields = _candidate_projection(relations)

        if (
            relations["employer_origin_candidate_gate_reviews"]
            and relations["employer_origin_source_candidates"]
        ):
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select
                        r.candidate_id,
                        {candidate_fields},
                        r.gate_name,
                        r.gate_status,
                        r.decision,
                        r.stop_reason,
                        r.reviewed_by,
                        greatest(
                            coalesce(r.reviewed_at, r.created_at),
                            r.updated_at,
                            r.created_at
                        ) as created_at
                    from employer_origin_candidate_gate_reviews r
                    join employer_origin_source_candidates c
                      on c.id = r.candidate_id
                    {candidate_join}
                    where r.gate_name in (
                        'detail_evidence_gate',
                        'connector_candidate_gate',
                        'connector_validation_gate',
                        'final_approval_gate',
                        'controlled_activation_gate',
                        'bronze_validation',
                        'silver_validation',
                        'source_lifecycle_tracking'
                    )
                    order by created_at desc, r.gate_order desc
                    limit 120
                    """
                )
                review_rows = list(cur.fetchall())

        if (
            relations["employer_origin_candidate_gate_events"]
            and relations["employer_origin_source_candidates"]
        ):
            review_join = ""
            gate_name = "null::text as gate_name"
            if relations["employer_origin_candidate_gate_reviews"]:
                review_join = (
                    "left join employer_origin_candidate_gate_reviews r "
                    "on r.id = e.gate_review_id"
                )
                gate_name = "r.gate_name"
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select
                        e.candidate_id,
                        {candidate_fields},
                        e.gate_review_id,
                        {gate_name},
                        e.event_type,
                        e.previous_state,
                        e.new_state,
                        e.event_reason,
                        e.created_at,
                        e.created_by
                    from employer_origin_candidate_gate_events e
                    join employer_origin_source_candidates c
                      on c.id = e.candidate_id
                    {candidate_join}
                    {review_join}
                    order by e.created_at desc, e.id desc
                    limit 160
                    """
                )
                event_rows = [dict(row) for row in cur.fetchall()]

    reviews = _runtime._rows_to_agent_gate_reviews(review_rows)
    return GateSignalCollection(
        reviews,
        events=event_rows,
        relations={name: relations[name] for name in relation_names},
    )


def load_orchestrator_attention_steps() -> OrchestratorSignalCollection:
    relation_names = (
        "gold_search_intelligence_orchestrator_latest_run",
        "gold_search_intelligence_orchestrator_attention_steps",
        "search_intelligence_orchestrator_runs",
        "search_intelligence_orchestrator_steps",
    )
    with psycopg.connect(
        _runtime.DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        relations = _relation_map(conn, relation_names)
        latest_run: dict[str, object] | None = None
        attention_rows: list[object] = []
        all_step_rows: list[object] = []

        if relations["gold_search_intelligence_orchestrator_latest_run"]:
            with conn.cursor() as cur:
                cur.execute(
                    "select * from gold_search_intelligence_orchestrator_latest_run"
                )
                row = cur.fetchone()
                latest_run = dict(row) if row else None
        elif relations["search_intelligence_orchestrator_runs"]:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        id as run_id,
                        cycle_name,
                        run_mode,
                        requested_by,
                        status as run_status,
                        started_at,
                        completed_at,
                        created_at,
                        summary,
                        guardrails
                    from search_intelligence_orchestrator_runs
                    order by created_at desc, id desc
                    limit 1
                    """
                )
                row = cur.fetchone()
                latest_run = dict(row) if row else None

        if latest_run and relations["search_intelligence_orchestrator_steps"]:
            run_id = latest_run.get("run_id") or latest_run.get("id")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        run_id,
                        step_order,
                        step_name,
                        step_status,
                        action_mode,
                        recommendation,
                        reason,
                        metrics,
                        completed_at
                    from search_intelligence_orchestrator_steps
                    where run_id = %s
                    order by step_order
                    """,
                    (run_id,),
                )
                all_step_rows = list(cur.fetchall())

        if relations["gold_search_intelligence_orchestrator_attention_steps"]:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        run_id,
                        step_order,
                        step_name,
                        step_status,
                        action_mode,
                        recommendation,
                        reason,
                        metrics,
                        completed_at
                    from gold_search_intelligence_orchestrator_attention_steps
                    order by attention_priority, step_order
                    limit 40
                    """
                )
                attention_rows = list(cur.fetchall())
        elif all_step_rows:
            attention_rows = [
                row
                for row in all_step_rows
                if str(_runtime._value(row, "step_status", ""))
                in {"attention_required", "blocked", "not_ready", "deferred"}
            ]

    all_steps = _runtime._rows_to_orchestrator_steps(all_step_rows)
    attention = _runtime._rows_to_orchestrator_steps(attention_rows)
    return OrchestratorSignalCollection(
        attention,
        latest_run=latest_run,
        all_steps=all_steps,
        relations={name: relations[name] for name in relation_names},
    )


# The retained handler resolves these names from its defining module at runtime.
_runtime.load_agent_gate_reviews = load_agent_gate_reviews
_runtime.load_orchestrator_attention_steps = load_orchestrator_attention_steps


def main() -> None:
    _runtime.main()


def __getattr__(name: str) -> object:
    """Preserve the public API of the retained runtime module."""

    return getattr(_runtime, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_runtime)))


if __name__ == "__main__":
    main()
