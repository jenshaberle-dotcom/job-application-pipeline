from __future__ import annotations

from scripts.run_f4a_r7_skill_reliability_audit import (
    _aggregate,
    _is_incremental,
    _requirement_surface_signal,
)


def test_requirement_surface_signal_covers_german_and_english_requirement_sections() -> None:
    assert _requirement_surface_signal("Dein Profil: Erfahrung mit EBICS und agilen Methoden")
    assert _requirement_surface_signal("Requirements: Python, SQL and cloud experience")
    assert not _requirement_surface_signal("Wir bieten Kaffee, Obst und ein modernes Büro")


def test_incremental_skill_comparison_is_conservative() -> None:
    assert not _is_incremental("Python", ["python"])
    assert not _is_incremental("Machine Learning", ["Machine Learning / AI"])
    assert _is_incremental("EBICS Zahlungsverkehr", ["Python", "SQL"])


def test_source_aggregation_surfaces_within_family_recall_risk() -> None:
    rows = [
        {
            "source_name": "Finanz Informatik",
            "structured_jobposting_found": True,
            "requirement_section_signal": True,
            "skill_count": 0,
            "skill_recall_risk": True,
            "external_incremental_skill_count": 3,
        },
        {
            "source_name": "Finanz Informatik",
            "structured_jobposting_found": True,
            "requirement_section_signal": True,
            "skill_count": 2,
            "skill_recall_risk": False,
            "external_incremental_skill_count": 1,
        },
        {
            "source_name": "Valuny",
            "structured_jobposting_found": True,
            "requirement_section_signal": True,
            "skill_count": 5,
            "skill_recall_risk": False,
            "external_incremental_skill_count": 0,
        },
    ]

    result = _aggregate(rows, "source_name")
    fi = result["Finanz Informatik"]
    assert fi["job_count"] == 2
    assert fi["skill_observed_job_count"] == 1
    assert fi["skill_recall_risk_count"] == 1
    assert fi["skill_observed_on_requirement_signal_ratio"] == 0.5
    assert fi["external_incremental_job_count"] == 2
    assert fi["external_incremental_skill_count"] == 4

    valuny = result["Valuny"]
    assert valuny["skill_observed_on_requirement_signal_ratio"] == 1.0
    assert valuny["skill_recall_risk_count"] == 0
