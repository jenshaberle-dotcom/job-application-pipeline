"""Preview S7O connector build candidate queue.

Boundary: read-only reporting helper. It does not build connector artifacts,
approve build requests, register connectors, activate sources, write Bronze
records or change scheduler configuration.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _print_summary(row: dict[str, Any] | None) -> None:
    print("S7O Connector Build Candidate Queue")
    print("boundary: read-only, no connector build, no registration, no activation, no Bronze write")
    print("---")
    if row is None:
        print("queued_candidate_count: 0")
        return
    for key, value in row.items():
        print(f"{key}: {value}")


def main() -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("select * from gold_connector_build_queue_summary;")
            _print_summary(cur.fetchone())

            print("---")
            print("Queue items")
            cur.execute(
                """
                select
                    queue_priority,
                    company_key,
                    display_company_name,
                    queue_action,
                    feasibility_status,
                    url_quality_status,
                    job_detail_candidate_evidence_count,
                    structural_job_evidence_count,
                    url_repair_candidate_url,
                    recommended_command_or_review
                from gold_connector_build_candidate_queue
                order by queue_priority, last_signal_at desc nulls last, display_company_name
                limit 20;
                """
            )
            rows = cur.fetchall()
            if not rows:
                print("- no connector build queue items")
                return
            for row in rows:
                repair = f" | repair={row['url_repair_candidate_url']}" if row["url_repair_candidate_url"] else ""
                command = f" | next={row['recommended_command_or_review']}" if row["recommended_command_or_review"] else ""
                print(
                    "- p{queue_priority} {display_company_name} [{company_key}] | action={queue_action} | "
                    "feasibility={feasibility_status} | url_quality={url_quality_status} | "
                    "job_detail={job_detail_candidate_evidence_count} | structural={structural_job_evidence_count}"
                    "{repair}{command}".format(repair=repair, command=command, **row)
                )


if __name__ == "__main__":
    main()
