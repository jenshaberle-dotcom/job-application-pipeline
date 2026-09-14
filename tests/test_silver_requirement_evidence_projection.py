from pathlib import Path

from src.silver.requirement_evidence_projection import (
    SILVER_REQUIREMENT_EVIDENCE_SCHEMA,
    build_silver_requirement_evidence,
    requirement_evidence_hash,
)


MIGRATION = Path("db/migrations/110_create_silver_job_requirement_evidence.sql")


def _raw_job(**overrides: object) -> dict[str, object]:
    raw_data = {
        "job": {
            "title": "Data Platform Engineer (m/w/d)",
            "source_url": "https://jobs.example.test/data-platform",
            "skills": ["Python", "Kubernetes"],
            "metadata": {
                "employment_types": ["FULL_TIME"],
                "workplace_type": "remote",
            },
        },
        "detail_evidence": {
            "schema": "generic_job_detail_evidence_v1",
            "methods": ["extruct:json-ld"],
            "parser_family": "schema_org_json_ld",
            "structured_jobposting_found": True,
            "description_excerpt": (
                "Sehr gute Deutschkenntnisse auf C1-Niveau. "
                "38 Stunden pro Woche. Python und Kubernetes."
            ),
            "description_source": "json-ld",
            "employment_types": ["FULL_TIME"],
            "skills": ["Python", "Kubernetes"],
            "remote": True,
            "raw_html_persisted": False,
        },
    }
    result: dict[str, object] = {
        "id": 314,
        "source_name": "generic_origin:example",
        "source_url": "https://jobs.example.test/data-platform",
        "raw_data": raw_data,
    }
    result.update(overrides)
    return result


def test_projection_carries_structured_and_bounded_bronze_truth() -> None:
    payload = build_silver_requirement_evidence(_raw_job())

    assert payload["schema"] == SILVER_REQUIREMENT_EVIDENCE_SCHEMA
    assert payload["parser_family"] == "schema_org_json_ld"
    assert payload["structured_jobposting_found"] is True
    assert payload["raw_html_persisted"] is False

    fields = payload["fields"]
    assert fields["job_skills"]["status"] == "observed_structured"
    assert fields["job_skills"]["values"] == ["Python", "Kubernetes"]
    assert fields["work_model"]["status"] == "observed_structured"
    assert fields["work_model"]["value"] == "remote"
    assert fields["required_languages"]["status"] == "observed_bounded_text"
    assert fields["required_languages"]["values"] == ["de"]
    assert fields["weekly_hours"]["status"] == "observed_bounded_text"
    assert fields["weekly_hours"]["minimum"] == 38.0
    assert fields["weekly_hours"]["maximum"] == 38.0


def test_projection_does_not_promote_structured_full_time_to_permanent_contract() -> None:
    payload = build_silver_requirement_evidence(_raw_job())
    employment = payload["fields"]["employment_type"]

    assert employment["value"] == "unknown"
    assert employment["source_employment_types"] == ["FULL_TIME"]
    assert employment["status"] == "source_absent_or_unresolved"


def test_projection_rejects_weak_trainee_shell_text_for_non_trainee_title() -> None:
    raw = _raw_job()
    raw["raw_data"]["detail_evidence"]["description_excerpt"] = (
        "Traineeprogramm. Sehr gute Deutschkenntnisse auf C1-Niveau."
    )
    payload = build_silver_requirement_evidence(raw)

    employment = payload["fields"]["employment_type"]
    assert employment["value"] == "unknown"
    assert employment["status"] == "source_absent_or_unresolved"


def test_projection_maps_explicit_partial_mobile_work_to_hybrid() -> None:
    raw = _raw_job()
    raw["raw_data"]["job"]["metadata"].pop("workplace_type")
    raw["raw_data"]["detail_evidence"]["remote"] = None
    raw["raw_data"]["detail_evidence"]["description_excerpt"] = (
        "Anteilige mobile Arbeit möglich. Python und Kubernetes."
    )
    payload = build_silver_requirement_evidence(raw)

    work_model = payload["fields"]["work_model"]
    assert work_model["value"] == "hybrid"
    assert work_model["status"] == "observed_bounded_text"


def test_projection_fails_closed_on_structured_vs_text_work_model_conflict() -> None:
    raw = _raw_job()
    raw["raw_data"]["detail_evidence"]["description_excerpt"] = (
        "Die Tätigkeit ist on-site und wird vor Ort ausgeübt."
    )
    payload = build_silver_requirement_evidence(raw)

    work_model = payload["fields"]["work_model"]
    assert work_model["value"] == "unknown"
    assert work_model["status"] == "conflict"
    assert "work_model" in payload["conflicted_fields"]


def test_projection_uses_bounded_text_skill_fallback_when_structured_skills_absent() -> None:
    raw = _raw_job()
    raw["raw_data"]["job"].pop("skills")
    raw["raw_data"]["detail_evidence"]["skills"] = []
    payload = build_silver_requirement_evidence(raw)

    skills = payload["fields"]["job_skills"]
    assert skills["status"] == "observed_bounded_text"
    assert skills["values"] == ["Python", "Kubernetes"]


def test_projection_is_deterministic_and_authority_free() -> None:
    first = build_silver_requirement_evidence(_raw_job())
    second = build_silver_requirement_evidence(_raw_job())

    assert requirement_evidence_hash(first) == requirement_evidence_hash(second)
    assert first["authority"] == {
        "job_source_evidence_only": True,
        "candidate_fact_authority": False,
        "capability_fit_authority": False,
        "hard_filter_authority": False,
        "ranking_authority": False,
        "top5_authority": False,
        "application_authority": False,
    }


def test_missing_bronze_detail_is_explicit_not_assumed() -> None:
    payload = build_silver_requirement_evidence(
        {
            "id": 315,
            "source_name": "personio:example",
            "source_url": "https://example.test/jobs/315",
            "raw_data": {"job": {"title": "Data Engineer"}},
        }
    )

    assert payload["parser_family"] == "unclassified"
    for field in payload["fields"].values():
        assert field["status"] == "source_absent_or_unresolved"


def test_migration_is_schema_only_bounded_sidecar() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists silver_job_requirement_evidence" in sql
    assert "silver_job_id bigint primary key" in sql
    assert "evidence_payload jsonb not null" in sql
    assert "raw_html_persisted" in sql
    assert "insert into silver_job_requirement_evidence" not in sql
    assert "update silver_jobs" not in sql
