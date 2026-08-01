"""Write a deterministic SI-022B1 origin projection from PostgreSQL read models."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.origin_inventory_projection import (
    project_origin_observations,
    read_current_origin_observations,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Project approved employer-origin observations into the deterministic "
            "SI-022A review contract without database writes."
        )
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    return parser


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as connection:
        rows = read_current_origin_observations(connection)
    projection = project_origin_observations(rows, as_of=args.as_of)
    payload = projection.to_json()
    _write_json(args.output, payload)
    print(
        "origin_inventory_projection_complete: "
        f"companies={payload['company_count']} "
        f"resolved={payload['resolved_company_count']} "
        f"needs_inspection={payload['needs_inspection_company_count']} "
        f"output={args.output}"
    )
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
