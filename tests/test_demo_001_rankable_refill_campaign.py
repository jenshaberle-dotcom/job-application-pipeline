from __future__ import annotations

import json
from pathlib import Path

import scripts.run_product_v1_rankable_refill_campaign as campaign


def _selected_rows() -> list[dict[str, object]]:
    return [
        {
            "silver_job_id": 655,
            "product_readiness_status": "assessment_required",
        },
        {
            "silver_job_id": 646,
            "product_readiness_status": "assessment_required",
        },
        {
            "silver_job_id": 593,
            "product_readiness_status": "hard_filter_evidence_required",
        },
        {
            "silver_job_id": 999,
            "product_readiness_status": "rankable",
        },
    ]


def test_materialization_plan_targets_only_missing_assessments(
    monkeypatch, tmp_path: Path
) -> None:
    output = tmp_path / "materialization.json"
    monkeypatch.setattr(campaign, "MATERIALIZATION_OUTPUT", output)
    calls: list[list[str]] = []

    def fake_run(command, check):
        calls.append(list(command))
        output.write_text(
            json.dumps(
                {
                    "proposal_count": 2,
                    "blocked_count": 0,
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(campaign.subprocess, "run", fake_run)

    planned, inserted = campaign._materialize_missing(
        _selected_rows(),
        apply=False,
    )

    assert planned == 2
    assert inserted == 0
    command = calls[0]
    assert command.count("--silver-job-id") == 2
    assert "655" in command
    assert "646" in command
    assert "593" not in command
    assert "999" not in command
    assert "--role-relevant-only" in command
    assert "--apply" not in command


def test_materialization_apply_reuses_generic_insert_only_authority(
    monkeypatch, tmp_path: Path
) -> None:
    output = tmp_path / "materialization.json"
    monkeypatch.setattr(campaign, "MATERIALIZATION_OUTPUT", output)
    calls: list[list[str]] = []

    def fake_run(command, check):
        calls.append(list(command))
        output.write_text(
            json.dumps(
                {
                    "proposal_count": 2,
                    "blocked_count": 0,
                    "apply_result": {
                        "inserted": 2,
                        "already_materialized": 0,
                    },
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(campaign.subprocess, "run", fake_run)

    planned, inserted = campaign._materialize_missing(
        _selected_rows(),
        apply=True,
    )

    assert planned == 2
    assert inserted == 2
    command = calls[0]
    assert "--apply" in command
    token_index = command.index("--approval-token") + 1
    assert command[token_index] == campaign.MATERIALIZATION_APPROVAL_TOKEN


def test_campaign_has_no_direct_assessment_or_ranking_sql() -> None:
    source = Path(
        "scripts/run_product_v1_rankable_refill_campaign.py"
    ).read_text(encoding="utf-8").casefold()

    assert "insert into job_product_assessments" not in source
    assert "update job_product_assessments" not in source
    assert "insert into gold_product_v1_top_jobs" not in source
    assert "update gold_product_v1_top_jobs" not in source
    assert "scripts.run_product_v1_assessment_materialization" in source
    assert "scripts.run_product_v1_rankable_refill_apply" in source
