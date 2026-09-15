from __future__ import annotations

import pytest

from scripts.build_f4a_r7_skill_annotation_seed import build_seed


def _report() -> dict[str, object]:
    return {
        "schema": "job_application_pipeline.f4a_r7_skill_reliability_audit.v2",
        "mode": "read_only",
        "rows": [
            {
                "silver_job_id": 11,
                "source_name": "source:a",
                "source_host": "jobs.example-a.test",
                "title": "Data Engineer",
                "requirement_section_text": "Experience with Python and SQL.",
                "skills": ["Python"],
                "external_incremental_skill_spans": ["SQL"],
                "skill_recall_risk": False,
            },
            {
                "silver_job_id": 12,
                "source_name": "source:a",
                "source_host": "jobs.example-a.test",
                "title": "Platform Engineer",
                "requirement_section_text": "Knowledge of Kubernetes.",
                "skills": [],
                "external_incremental_skill_spans": ["Kubernetes"],
                "skill_recall_risk": True,
            },
            {
                "silver_job_id": 21,
                "source_name": "source:b",
                "source_host": "jobs.example-b.test",
                "title": "Unavailable section",
                "requirement_section_text": "",
                "skills": [],
                "external_incremental_skill_spans": [],
                "skill_recall_risk": False,
            },
        ],
    }


def test_build_seed_preserves_text_candidates_and_employer_holdout_group() -> None:
    seed = build_seed(_report())

    assert seed["record_count"] == 2
    assert seed["split_group_count"] == 1
    assert seed["split_groups"] == {"jobs.example-a.test": 2}
    first = seed["records"][0]
    assert first["split_group"] == "jobs.example-a.test"
    assert first["requirement_text"] == "Experience with Python and SQL."
    assert first["deterministic_skills"] == ["Python"]
    assert first["shadow_candidates"] == ["SQL"]
    assert len(first["requirement_text_sha256"]) == 64
    assert first["gold_spans"] == []
    assert first["negative_spans"] == []
    assert first["annotation_status"] == "unreviewed"
    assert not any(seed["boundaries"].values())


def test_build_seed_rejects_non_read_only_or_wrong_schema() -> None:
    report = _report()
    report["mode"] = "write"
    with pytest.raises(ValueError, match="read-only"):
        build_seed(report)

    report = _report()
    report["schema"] = "other"
    with pytest.raises(ValueError, match="unsupported"):
        build_seed(report)
