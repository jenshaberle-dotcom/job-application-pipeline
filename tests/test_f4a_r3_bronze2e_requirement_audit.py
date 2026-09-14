from copy import deepcopy

from scripts.product_v1_silver_requirement_projection import (
    project_silver_requirement_evidence,
)
from scripts.run_f4a_r3_bronze2e_requirement_audit import build_report
from src.silver.requirement_evidence_projection import (
    build_silver_requirement_evidence,
    requirement_evidence_hash,
)


def _raw_job(*, with_detail: bool = True) -> dict[str, object]:
    raw_data: dict[str, object] = {
        "job": {
            "title": "Data Engineer",
            "source_url": "https://jobs.example.test/10",
            "skills": ["Python", "SQL"],
        }
    }
    if with_detail:
        raw_data["detail_evidence"] = {
            "schema": "generic_job_detail_evidence_v1",
            "parser_family": "schema_org_json_ld",
            "methods": ["extruct:json-ld"],
            "structured_jobposting_found": True,
            "skills": ["Python", "SQL"],
            "remote": True,
            "description_excerpt": "Sehr gute Deutschkenntnisse auf C1-Niveau.",
            "description_source": "json-ld",
        }
    return {
        "id": 20,
        "source_name": "generic_origin:example",
        "source_url": "https://jobs.example.test/10",
        "title": "Data Engineer",
        "raw_data": raw_data,
    }


def _operator_from_sidecar(sidecar: dict[str, object]) -> dict[str, object]:
    projected = project_silver_requirement_evidence(sidecar)
    assert projected is not None
    return {"silver_job_id": 10, **projected}


def _row(
    sidecar: dict[str, object],
    *,
    raw_job: dict[str, object] | None = None,
) -> dict[str, object]:
    source = raw_job or _raw_job()
    return {
        "silver_job_id": 10,
        "raw_job_id": 20,
        "source_name": "generic_origin:example",
        "source_url": "https://jobs.example.test/10",
        "title": "Data Engineer",
        "company_name": "Example GmbH",
        "raw_data": source["raw_data"],
        "normalized_evidence": None,
        "persisted_evidence_hash": requirement_evidence_hash(sidecar),
        "persisted_silver_requirement_evidence": sidecar,
    }


def test_audit_accepts_explicit_persisted_silver_operator_projection() -> None:
    sidecar = build_silver_requirement_evidence(_raw_job())
    report = build_report(
        [_row(sidecar)],
        operator_rows={10: _operator_from_sidecar(sidecar)},
    )

    assert report["candidate_count"] == 1
    assert report["operator_candidate_count"] == 1
    assert report["reachable_without_extractor_gap_ratio"] == 1.0
    assert report["rows_with_legacy_ambiguous_status"] == 0
    assert report["rows_with_silver_to_operator_projection_loss"] == 0
    assert report["violating_row_count"] == 0
    assert report["coverage_gate_pass"] is True


def test_audit_rejects_legacy_ambiguous_status() -> None:
    sidecar = build_silver_requirement_evidence(_raw_job())
    mutated = deepcopy(sidecar)
    mutated["fields"]["employment_type"]["status"] = "source_absent_or_unresolved"
    report = build_report(
        [_row(mutated)],
        operator_rows={10: _operator_from_sidecar(mutated)},
    )

    assert report["rows_with_legacy_ambiguous_status"] == 1
    assert report["violating_row_count"] == 1
    assert report["coverage_gate_pass"] is False


def test_audit_rejects_silver_to_operator_projection_loss() -> None:
    sidecar = build_silver_requirement_evidence(_raw_job())
    operator = _operator_from_sidecar(sidecar)
    operator["job_skills"] = []
    report = build_report([_row(sidecar)], operator_rows={10: operator})

    assert report["rows_with_silver_to_operator_projection_loss"] == 1
    assert report["violating_row_count"] == 1
    assert report["coverage_gate_pass"] is False


def test_audit_counts_missing_detail_contract_as_extractor_gap() -> None:
    raw_job = _raw_job(with_detail=False)
    sidecar = build_silver_requirement_evidence(raw_job)
    report = build_report(
        [_row(sidecar, raw_job=raw_job)],
        operator_rows={10: _operator_from_sidecar(sidecar)},
    )

    assert report["rows_with_extractor_gap"] == 1
    assert report["reachable_without_extractor_gap_ratio"] == 0.0
    assert report["coverage_gate_pass"] is False


def test_audit_boundaries_are_read_only_and_authority_free() -> None:
    sidecar = build_silver_requirement_evidence(_raw_job())
    report = build_report(
        [_row(sidecar)],
        operator_rows={10: _operator_from_sidecar(sidecar)},
    )

    assert report["boundaries"] == {
        "database_writes": 0,
        "provider_calls": 0,
        "candidate_fact_reads": 0,
        "ranking_authority": 0,
        "top5_authority": 0,
        "application_authority": 0,
        "raw_html_persisted": 0,
    }
