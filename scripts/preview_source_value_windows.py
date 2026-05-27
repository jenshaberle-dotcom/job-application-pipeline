"""Preview source-value snapshot windows.

This script is the first G1 window-function block. It intentionally reads only
from source_value_snapshots and does not create Gold tables or database views
yet.

Usage:
    python -m scripts.preview_source_value_windows --window-hours 24
    python -m scripts.preview_source_value_windows --window-days 7
    python -m scripts.preview_source_value_windows --window-days 30
    python -m scripts.preview_source_value_windows --all-default-windows
"""

from __future__ import annotations

import argparse
import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from numbers import Number
from pathlib import Path
from typing import Any

from src.config import get_database_config


DEFAULT_WINDOW_SPECS: tuple[tuple[str, int], ...] = (
    ("24h", 24 * 60 * 60),
    ("7d", 7 * 24 * 60 * 60),
    ("30d", 30 * 24 * 60 * 60),
)

WINDOW_PREVIEW_FIELDNAMES = [
    "window_label",
    "window_start",
    "window_end",
    "source_name",
    "source_family",
    "source_target",
    "source_type",
    "snapshot_count",
    "first_snapshot_at",
    "latest_snapshot_at",
    "first_snapshot_reason",
    "latest_snapshot_reason",
    "first_raw_jobs",
    "latest_raw_jobs",
    "raw_jobs_delta",
    "first_silver_jobs",
    "latest_silver_jobs",
    "silver_jobs_delta",
    "first_matched_jobs_after_filter",
    "latest_matched_jobs_after_filter",
    "matched_jobs_after_filter_delta",
    "first_duplicate_jobs",
    "latest_duplicate_jobs",
    "duplicate_jobs_delta",
    "first_duplicate_rate_pct",
    "latest_duplicate_rate_pct",
    "duplicate_rate_delta_pct",
    "first_failure_rate_pct",
    "latest_failure_rate_pct",
    "failure_rate_delta_pct",
    "latest_lifecycle_state",
    "latest_recommendation",
]


SOURCE_VALUE_WINDOW_SQL = """
WITH scoped_snapshots AS (
    SELECT *
    FROM source_value_snapshots
    WHERE snapshot_at >= %(window_start)s
      AND snapshot_at <= %(window_end)s
),
ranked AS (
    SELECT
        %(window_label)s::TEXT AS window_label,
        %(window_start)s::TIMESTAMPTZ AS window_start,
        %(window_end)s::TIMESTAMPTZ AS window_end,
        source_name,
        source_family,
        source_target,
        source_type,

        COUNT(*) OVER source_partition AS snapshot_count,
        MIN(snapshot_at) OVER source_partition AS first_snapshot_at,
        MAX(snapshot_at) OVER source_partition AS latest_snapshot_at,

        FIRST_VALUE(snapshot_reason) OVER source_ascending
            AS first_snapshot_reason,
        FIRST_VALUE(snapshot_reason) OVER source_descending
            AS latest_snapshot_reason,

        FIRST_VALUE(raw_jobs) OVER source_ascending AS first_raw_jobs,
        FIRST_VALUE(raw_jobs) OVER source_descending AS latest_raw_jobs,

        FIRST_VALUE(silver_jobs) OVER source_ascending AS first_silver_jobs,
        FIRST_VALUE(silver_jobs) OVER source_descending AS latest_silver_jobs,

        FIRST_VALUE(matched_jobs_after_filter) OVER source_ascending
            AS first_matched_jobs_after_filter,
        FIRST_VALUE(matched_jobs_after_filter) OVER source_descending
            AS latest_matched_jobs_after_filter,

        FIRST_VALUE(duplicate_jobs) OVER source_ascending
            AS first_duplicate_jobs,
        FIRST_VALUE(duplicate_jobs) OVER source_descending
            AS latest_duplicate_jobs,

        FIRST_VALUE(duplicate_rate_pct) OVER source_ascending
            AS first_duplicate_rate_pct,
        FIRST_VALUE(duplicate_rate_pct) OVER source_descending
            AS latest_duplicate_rate_pct,

        FIRST_VALUE(failure_rate_pct) OVER source_ascending
            AS first_failure_rate_pct,
        FIRST_VALUE(failure_rate_pct) OVER source_descending
            AS latest_failure_rate_pct,

        FIRST_VALUE(lifecycle_state) OVER source_descending
            AS latest_lifecycle_state,
        FIRST_VALUE(recommendation) OVER source_descending
            AS latest_recommendation,

        ROW_NUMBER() OVER (
            PARTITION BY source_name
            ORDER BY snapshot_at DESC, id DESC
        ) AS latest_rank
    FROM scoped_snapshots
    WINDOW
        source_partition AS (
            PARTITION BY source_name
        ),
        source_ascending AS (
            PARTITION BY source_name
            ORDER BY snapshot_at ASC, id ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ),
        source_descending AS (
            PARTITION BY source_name
            ORDER BY snapshot_at DESC, id DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
)
SELECT
    window_label,
    window_start,
    window_end,
    source_name,
    source_family,
    source_target,
    source_type,
    snapshot_count,
    first_snapshot_at,
    latest_snapshot_at,
    first_snapshot_reason,
    latest_snapshot_reason,
    first_raw_jobs,
    latest_raw_jobs,
    latest_raw_jobs - first_raw_jobs AS raw_jobs_delta,
    first_silver_jobs,
    latest_silver_jobs,
    latest_silver_jobs - first_silver_jobs AS silver_jobs_delta,
    first_matched_jobs_after_filter,
    latest_matched_jobs_after_filter,
    latest_matched_jobs_after_filter - first_matched_jobs_after_filter
        AS matched_jobs_after_filter_delta,
    first_duplicate_jobs,
    latest_duplicate_jobs,
    latest_duplicate_jobs - first_duplicate_jobs AS duplicate_jobs_delta,
    first_duplicate_rate_pct,
    latest_duplicate_rate_pct,
    latest_duplicate_rate_pct - first_duplicate_rate_pct
        AS duplicate_rate_delta_pct,
    first_failure_rate_pct,
    latest_failure_rate_pct,
    latest_failure_rate_pct - first_failure_rate_pct
        AS failure_rate_delta_pct,
    latest_lifecycle_state,
    latest_recommendation
FROM ranked
WHERE latest_rank = 1
ORDER BY window_label, source_name;
"""


@dataclass(frozen=True)
class WindowSpec:
    label: str
    seconds: int

    @property
    def duration(self) -> timedelta:
        return timedelta(seconds=self.seconds)


def build_window_spec_from_hours(hours: int) -> WindowSpec:
    if hours <= 0:
        raise ValueError("window-hours must be greater than zero")

    return WindowSpec(label=f"{hours}h", seconds=hours * 60 * 60)


def build_window_spec_from_days(days: int) -> WindowSpec:
    if days <= 0:
        raise ValueError("window-days must be greater than zero")

    return WindowSpec(label=f"{days}d", seconds=days * 24 * 60 * 60)


def default_window_specs() -> list[WindowSpec]:
    return [WindowSpec(label=label, seconds=seconds) for label, seconds in DEFAULT_WINDOW_SPECS]


def select_window_specs(
    window_hours: int | None,
    window_days: int | None,
    all_default_windows: bool,
) -> list[WindowSpec]:
    selected = [
        value is not None
        for value in (
            window_hours,
            window_days,
        )
    ]

    if all_default_windows and any(selected):
        raise ValueError(
            "--all-default-windows cannot be combined with --window-hours or --window-days"
        )

    if window_hours is not None and window_days is not None:
        raise ValueError("--window-hours and --window-days are mutually exclusive")

    if all_default_windows:
        return default_window_specs()

    if window_hours is not None:
        return [build_window_spec_from_hours(window_hours)]

    if window_days is not None:
        return [build_window_spec_from_days(window_days)]

    return default_window_specs()


def build_window_params(
    window_spec: WindowSpec,
    window_end: datetime,
) -> dict[str, Any]:
    return {
        "window_label": window_spec.label,
        "window_start": window_end - window_spec.duration,
        "window_end": window_end,
    }


def numeric_delta(
    latest_value: int | float | None,
    first_value: int | float | None,
) -> int | float | None:
    if latest_value is None or first_value is None:
        return None

    return latest_value - first_value


def format_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.isoformat()

    return str(value)


def format_delta(value: Any) -> str:
    if value is None:
        return ""

    if value == 0:
        return "0"

    if isinstance(value, Number) and value > 0:
        return f"+{value}"

    return str(value)


def print_table(headers: list[str], rows: Sequence[Sequence[Any]]) -> None:
    if not rows:
        print("No rows.")
        return

    widths = [
        max(len(header), *(len(format_value(row[index])) for row in rows))
        for index, header in enumerate(headers)
    ]

    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))

    for row in rows:
        print(
            " | ".join(
                format_value(value).ljust(widths[index])
                for index, value in enumerate(row)
            )
        )


def load_window_rows(window_specs: Sequence[WindowSpec]) -> list[dict[str, Any]]:
    import psycopg
    from psycopg.rows import dict_row

    config = get_database_config()
    window_end = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    with psycopg.connect(**config) as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            for window_spec in window_specs:
                cursor.execute(
                    SOURCE_VALUE_WINDOW_SQL,
                    build_window_params(
                        window_spec=window_spec,
                        window_end=window_end,
                    ),
                )
                rows.extend(dict(row) for row in cursor.fetchall())

    return rows


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=WINDOW_PREVIEW_FIELDNAMES)
        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row.get(field)
                    for field in WINDOW_PREVIEW_FIELDNAMES
                }
            )


def print_window_preview(rows: list[dict[str, Any]]) -> None:
    print()
    print("Source Value Window Preview")
    print("Mode: read-only")
    print("Database cleanup action: none")
    print()

    table_rows: list[list[Any]] = []
    for row in rows:
        table_rows.append(
            [
                row["window_label"],
                row["source_name"],
                row["snapshot_count"],
                row["first_snapshot_at"],
                row["latest_snapshot_at"],
                row["latest_raw_jobs"],
                format_delta(row["raw_jobs_delta"]),
                row["latest_silver_jobs"],
                format_delta(row["silver_jobs_delta"]),
                row["latest_matched_jobs_after_filter"],
                format_delta(row["matched_jobs_after_filter_delta"]),
                row["latest_duplicate_rate_pct"],
                format_delta(row["duplicate_rate_delta_pct"]),
                row["latest_failure_rate_pct"],
                format_delta(row["failure_rate_delta_pct"]),
            ]
        )

    print_table(
        headers=[
            "window",
            "source_name",
            "snapshots",
            "first_snapshot_at",
            "latest_snapshot_at",
            "latest_raw",
            "raw_delta",
            "latest_silver",
            "silver_delta",
            "latest_matched",
            "matched_delta",
            "latest_dup_rate",
            "dup_rate_delta",
            "latest_failure_rate",
            "failure_rate_delta",
        ],
        rows=table_rows,
    )

    print()
    print("Interpretation boundary:")
    print("- This preview uses persisted source_value_snapshots only.")
    print("- It does not create Gold views, lifecycle scores or recommendations.")
    print("- Historical burden tracks must still be excluded in later Trend/Gold semantics.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--window-hours",
        type=int,
        help="Preview one rolling source-value window in hours, for example 24.",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        help="Preview one rolling source-value window in days, for example 7 or 30.",
    )
    parser.add_argument(
        "--all-default-windows",
        action="store_true",
        help="Preview the default 24h, 7d and 30d source-value windows.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        help="Optional directory for source_value_window_preview.csv.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        window_specs = select_window_specs(
            window_hours=args.window_hours,
            window_days=args.window_days,
            all_default_windows=args.all_default_windows,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    rows = load_window_rows(window_specs=window_specs)
    print_window_preview(rows=rows)

    if args.export_dir:
        export_path = args.export_dir / "source_value_window_preview.csv"
        write_csv(path=export_path, rows=rows)
        print()
        print("Exported source-value window preview:")
        print(f"- {export_path}")


if __name__ == "__main__":
    main()
