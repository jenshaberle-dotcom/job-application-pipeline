from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.provider001a_provider_backed_origin_preflight import (  # noqa: E402
    build_provider_backed_origin_preflight,
    write_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PROVIDER-001A provider-backed origin coverage preflight.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum employer-origin candidate rows to inspect.")
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=Path("exports/provider001a_provider_backed_origin_preflight"),
        help="Output directory for JSON/Markdown provider preflight artifacts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, db_status = fetch_employer_origin_candidate_rows(limit=args.limit)
    report = build_provider_backed_origin_preflight(rows, source=f"employer_origin_source_candidates:{db_status}")
    outputs = write_outputs(report, args.export_dir)
    summary = report.get("summary", {})
    print("# PROVIDER-001A Provider-backed Origin Coverage Preflight")
    print(f"db_status={db_status}")
    print(f"overall_status={report.get('overall_status')}")
    print(f"provider_backed_candidate_count={summary.get('provider_backed_candidate_count')}")
    print(f"provider_backed_candidate_keys={summary.get('provider_backed_candidate_keys')}")
    print(f"missing_gap_ids={summary.get('missing_gap_ids')}")
    print(f"next_action={report.get('next_action')}")
    print(f"json={outputs['json']}")
    print(f"markdown={outputs['markdown']}")
    return 0


def fetch_employer_origin_candidate_rows(*, limit: int) -> tuple[list[dict[str, object]], str]:
    try:
        import psycopg
        from psycopg.rows import dict_row

        from src.config import get_database_config

        with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        company_key,
                        company_name,
                        candidate_url,
                        source_name_candidate,
                        source_family_candidate,
                        source_target_candidate,
                        source_type_candidate,
                        status,
                        risk_level,
                        notes,
                        created_at,
                        updated_at
                    FROM employer_origin_source_candidates
                    ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                    LIMIT %(limit)s
                    """,
                    {"limit": int(limit)},
                )
                rows = [dict(row) for row in cur.fetchall()]
        return rows, f"ok_row_count_{len(rows)}"
    except Exception as exc:  # pragma: no cover - defensive for local environments without DB.
        return [], f"unavailable_{type(exc).__name__}"


if __name__ == "__main__":
    raise SystemExit(main())
