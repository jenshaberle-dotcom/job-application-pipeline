"""Preview Gold Search Intelligence read models.

Boundary: read-only reporting helper. It does not mutate search profiles, sources,
Bronze, Silver, scheduler state or approval state.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


def connect() -> psycopg.Connection[Any]:
    """Connect using the project-standard POSTGRES_* environment contract.

    The project already centralizes .env loading and PostgreSQL settings in
    src.config.get_database_config(). This preview helper must not introduce a
    second DB environment naming scheme.
    """

    return psycopg.connect(
        **get_database_config(),
        row_factory=dict_row,
    )


def print_kv(row: dict[str, Any]) -> None:
    for key, value in row.items():
        print(f"{key}: {value}")


def main() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            print("Gold Search Intelligence Preview")
            print("boundary: read-only, no source activation, no Bronze write, no scheduler change")
            print("---")

            cur.execute("select * from gold_market_coverage_summary;")
            summary = cur.fetchone()
            if summary:
                print_kv(dict(summary))

            print("---")
            print("Top candidate lifecycle items")
            cur.execute(
                """
                select
                    company_key,
                    display_company_name,
                    current_stage,
                    fn_pressure_level,
                    passed_gate_count,
                    total_gate_count,
                    blocking_gate,
                    recommended_next_action
                from gold_candidate_lifecycle_status
                order by
                    case current_stage
                        when 'build_approval_required' then 1
                        when 'gate_reassessment_required' then 2
                        when 'blocked_by_gate' then 3
                        when 'connector_artifact_generation_allowed' then 4
                        when 'active_controlled' then 5
                        else 9
                    end,
                    last_signal_at desc nulls last,
                    display_company_name
                limit 10;
                """
            )
            for row in cur.fetchall():
                print(
                    "- {display_company_name} [{company_key}] | stage={current_stage} | "
                    "fn_pressure={fn_pressure_level} | gates={passed_gate_count}/{total_gate_count} | "
                    "blocker={blocking_gate} | next={recommended_next_action}".format(**row)
                )

            print("---")
            print("Approval queue")
            cur.execute(
                """
                select
                    approval_type,
                    display_company_name,
                    current_stage,
                    fn_pressure_level,
                    recommendation
                from gold_approval_queue
                order by last_signal_at desc nulls last, display_company_name
                limit 10;
                """
            )
            rows = cur.fetchall()
            if not rows:
                print("- no approval items")
            for row in rows:
                print(
                    "- {approval_type}: {display_company_name} | stage={current_stage} | "
                    "fn_pressure={fn_pressure_level} | recommendation={recommendation}".format(**row)
                )


if __name__ == "__main__":
    main()
