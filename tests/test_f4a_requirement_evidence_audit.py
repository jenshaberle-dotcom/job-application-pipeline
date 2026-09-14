from __future__ import annotations

from scripts.run_f4a_requirement_evidence_audit import _sample_rows, _source_family


def _row(source_name: str, silver_job_id: int) -> dict[str, object]:
    return {"source_name": source_name, "silver_job_id": silver_job_id}


def test_source_family_normalization_keeps_generic_origin_together() -> None:
    assert _source_family("personio:eraneos") == "personio"
    assert _source_family("greenhouse:stripe") == "greenhouse"
    assert _source_family("generic_origin:finanz_informatik") == "generic_origin"


def test_sample_rows_continues_across_source_families() -> None:
    rows = [
        _row("greenhouse:alpha", 1),
        _row("greenhouse:beta", 2),
        _row("personio:alpha", 3),
        _row("personio:beta", 4),
    ]

    sample = _sample_rows(rows, max_per_family=1, max_jobs=10)

    assert [row["silver_job_id"] for row in sample] == [1, 3]
    assert {_source_family(row["source_name"]) for row in sample} == {
        "greenhouse",
        "personio",
    }


def test_sample_rows_round_robins_source_names_within_family() -> None:
    rows = [
        _row("personio:alpha", 1),
        _row("personio:alpha", 2),
        _row("personio:beta", 3),
        _row("personio:beta", 4),
    ]

    sample = _sample_rows(rows, max_per_family=3, max_jobs=10)

    assert [row["silver_job_id"] for row in sample] == [1, 3, 2]


def test_sample_rows_respects_global_job_cap() -> None:
    rows = [
        _row("greenhouse:alpha", 1),
        _row("personio:alpha", 2),
        _row("workday:alpha", 3),
    ]

    sample = _sample_rows(rows, max_per_family=5, max_jobs=2)

    assert len(sample) == 2
