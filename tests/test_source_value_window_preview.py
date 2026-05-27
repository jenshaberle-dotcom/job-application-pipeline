from __future__ import annotations

import csv
from datetime import datetime, timezone

import pytest

from scripts.preview_source_value_windows import (
    WINDOW_PREVIEW_FIELDNAMES,
    WindowSpec,
    build_interpretation_warning,
    build_window_params,
    build_window_spec_from_days,
    build_window_spec_from_hours,
    calculate_observed_window_coverage_pct,
    calculate_observed_window_hours,
    classify_trend_maturity,
    default_window_specs,
    enrich_window_row,
    format_delta,
    numeric_delta,
    select_window_specs,
    write_csv,
)


def test_default_window_specs_are_24h_7d_30d() -> None:
    specs = default_window_specs()

    assert [spec.label for spec in specs] == ["24h", "7d", "30d"]
    assert [spec.seconds for spec in specs] == [
        24 * 60 * 60,
        7 * 24 * 60 * 60,
        30 * 24 * 60 * 60,
    ]


def test_build_window_spec_from_hours() -> None:
    spec = build_window_spec_from_hours(24)

    assert spec == WindowSpec(label="24h", seconds=24 * 60 * 60)


def test_build_window_spec_from_days() -> None:
    spec = build_window_spec_from_days(7)

    assert spec == WindowSpec(label="7d", seconds=7 * 24 * 60 * 60)


def test_window_specs_must_be_positive() -> None:
    with pytest.raises(ValueError, match="window-hours"):
        build_window_spec_from_hours(0)

    with pytest.raises(ValueError, match="window-days"):
        build_window_spec_from_days(0)


def test_select_window_specs_defaults_to_all_default_windows() -> None:
    specs = select_window_specs(
        window_hours=None,
        window_days=None,
        all_default_windows=False,
    )

    assert [spec.label for spec in specs] == ["24h", "7d", "30d"]


def test_select_window_specs_rejects_ambiguous_selection() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        select_window_specs(
            window_hours=24,
            window_days=7,
            all_default_windows=False,
        )

    with pytest.raises(ValueError, match="all-default-windows"):
        select_window_specs(
            window_hours=24,
            window_days=None,
            all_default_windows=True,
        )


def test_build_window_params_uses_stable_window_end() -> None:
    window_end = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)

    params = build_window_params(
        window_spec=WindowSpec(label="24h", seconds=24 * 60 * 60),
        window_end=window_end,
    )

    assert params["window_label"] == "24h"
    assert params["window_end"] == window_end
    assert params["window_start"] == datetime(2026, 5, 26, 12, 0, tzinfo=timezone.utc)


def test_numeric_delta_handles_missing_values() -> None:
    assert numeric_delta(10, 7) == 3
    assert numeric_delta(7, 10) == -3
    assert numeric_delta(None, 10) is None
    assert numeric_delta(10, None) is None


def test_format_delta_is_human_readable() -> None:
    assert format_delta(3) == "+3"
    assert format_delta(0) == "0"
    assert format_delta(-3) == "-3"
    assert format_delta(None) == ""




def test_observed_window_helpers_calculate_coverage() -> None:
    first_snapshot_at = datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc)
    latest_snapshot_at = datetime(2026, 5, 27, 20, 0, tzinfo=timezone.utc)

    observed_hours = calculate_observed_window_hours(
        first_snapshot_at=first_snapshot_at,
        latest_snapshot_at=latest_snapshot_at,
    )

    assert observed_hours == 12.0
    assert calculate_observed_window_coverage_pct(
        observed_window_hours=observed_hours,
        requested_window_hours=24.0,
    ) == 50.0


def test_trend_maturity_classification_is_conservative() -> None:
    assert classify_trend_maturity(0, None) == "no_snapshots"
    assert classify_trend_maturity(1, 100.0) == "single_snapshot_only"
    assert classify_trend_maturity(2, 100.0) == "low_snapshot_count"
    assert classify_trend_maturity(3, 25.0) == "low_window_coverage"
    assert classify_trend_maturity(3, 75.0) == "partial_window_coverage"
    assert classify_trend_maturity(3, 100.0) == "mature_window"


def test_low_maturity_warning_is_explicit() -> None:
    warning = build_interpretation_warning(
        trend_maturity="low_snapshot_count",
        snapshot_count=2,
        observed_window_coverage_pct=75.0,
    )

    assert "Only 2 snapshots" in warning
    assert "not lifecycle trend" in warning


def test_enrich_window_row_adds_trend_maturity_fields() -> None:
    row = {
        "snapshot_count": 2,
        "first_snapshot_at": datetime(2026, 5, 27, 8, 0, tzinfo=timezone.utc),
        "latest_snapshot_at": datetime(2026, 5, 27, 20, 0, tzinfo=timezone.utc),
    }

    enriched = enrich_window_row(
        row=row,
        window_spec=WindowSpec(label="24h", seconds=24 * 60 * 60),
    )

    assert enriched["requested_window_hours"] == 24.0
    assert enriched["observed_window_hours"] == 12.0
    assert enriched["observed_window_coverage_pct"] == 50.0
    assert enriched["trend_maturity"] == "low_snapshot_count"
    assert "not lifecycle trend" in enriched["interpretation_warning"]


def test_write_csv_includes_header_for_empty_rows(tmp_path) -> None:
    export_path = tmp_path / "source_value_window_preview.csv"

    write_csv(export_path, rows=[])

    with export_path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    assert reader.fieldnames == WINDOW_PREVIEW_FIELDNAMES
    assert rows == []
