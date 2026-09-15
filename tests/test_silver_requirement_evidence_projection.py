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
                "Wir suchen Verstärkung für unser Team. Du arbeitest mit Python und "
                "Kubernetes. Sehr gute Deutschkenntnisse auf C1-Niveau. "
                "38 Stunden pro Woche. Deine Erfahrung und Kenntnisse sind wichtig."
            ),
            "description_source": "json-ld",
            "requirement_text_excerpt": (
                "Wir suchen Verstärkung für unser Team. Du arbeitest mit Python und "
                "Kubernetes. Sehr gute Deutschkenntnisse auf C1-Niveau. "
                "38 Stunden pro Woche. Deine Erfahrung und Kenntnisse sind wichtig."
            ),
            "requirement_text_source": "json-ld",
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

    display = payload["display_context"]
    assert display["employment_scope"] == "full_time"
    assert display["employment_scope_status"] == "observed_structured"
    assert display["posting_language"] == "de"
    assert display["posting_language_basis"] == "bounded_visible_vacancy_text"
    assert display["hard_filter_authority"] is False
    assert display["observer_authority"] is False


def test_projection_classifies_semantically_unsupported_structured_employment_as_source_absent() -> None:
    payload = build_silver_requirement_evidence(_raw_job())
    employment = payload["fields"]["employment_type"]

    assert employment["value"] == "unknown"
    assert employment["source_employment_types"] == ["FULL_TIME"]
    assert employment["status"] == "source_absent"
    assert payload["display_context"]["employment_scope"] == "full_time"


def test_title_seniority_is_display_context_not_requirement_authority() -> None:
    raw = _raw_job()
    raw["raw_data"]["job"]["title"] = "Senior Data Platform Engineer"
    payload = build_silver_requirement_evidence(raw)

    assert payload["fields"]["requirements_seniority"]["value"] == "unknown"
    assert payload["display_context"]["title_seniority_signal"] == "senior"
    assert payload["display_context"]["title_seniority_basis"] == "job_title"
    assert payload["display_context"]["hard_filter_authority"] is False


def test_posting_language_does_not_fabricate_explicit_language_requirement() -> None:
    raw = _raw_job()
    text = (
        "We are looking for an engineer for our team. You will work with Python and "
        "machine learning and take responsibility for our platform. Your experience "
        "and skills are important for this role and our application process."
    )
    raw["raw_data"]["detail_evidence"]["description_excerpt"] = text
    raw["raw_data"]["detail_evidence"]["requirement_text_excerpt"] = text
    payload = build_silver_requirement_evidence(raw)

    assert payload["fields"]["required_languages"]["values"] == []
    assert payload["display_context"]["posting_language"] == "en"


def test_projection_rejects_weak_trainee_shell_text_for_non_trainee_title() -> None:
    raw = _raw_job()
    raw["raw_data"]["detail_evidence"]["description_excerpt"] = (
        "Traineeprogramm. Sehr gute Deutschkenntnisse auf C1-Niveau."
    )
    raw["raw_data"]["detail_evidence"]["requirement_text_excerpt"] = (
        "Traineeprogramm. Sehr gute Deutschkenntnisse auf C1-Niveau."
    )
    payload = build_silver_requirement_evidence(raw)

    employment = payload["fields"]["employment_type"]
    assert employment["value"] == "unknown"
    assert employment["status"] == "source_absent"


def test_projection_maps_explicit_partial_mobile_work_to_hybrid() -> None:
    raw = _raw_job()
    raw["raw_data"]["job"]["metadata"].pop("workplace_type")
    raw["raw_data"]["detail_evidence"]["remote"] = None
    raw["raw_data"]["detail_evidence"]["description_excerpt"] = (
        "Anteilige mobile Arbeit möglich. Python und Kubernetes."
    )
    raw["raw_data"]["detail_evidence"]["requirement_text_excerpt"] = (
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
    raw["raw_data"]["detail_evidence"]["requirement_text_excerpt"] = (
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


def test_visible_origin_evidence_fills_hours_experience_compensation_and_mobile_context() -> None:
    raw = _raw_job()
    raw["raw_data"]["job"]["metadata"].pop("workplace_type")
    raw["raw_data"]["detail_evidence"]["remote"] = None
    raw["raw_data"]["detail_evidence"]["requirement_text_excerpt"] = (
        "Unterstützung der Endkunden in fachlichen Fragen."
    )
    raw["raw_data"]["detail_evidence"]["visible_text_excerpt"] = (
        "Business Analyst. Haustarifvertrag. 38 Stunden / Woche. "
        "Anteilige mobile Arbeit möglich. ab 59.417 € / Jahr. "
        "Abgeschlossenes Studium sowie mindestens 2-3 Jahre fachbezogene Berufserfahrung."
    )

    payload = build_silver_requirement_evidence(raw)

    weekly = payload["fields"]["weekly_hours"]
    assert weekly["status"] == "observed_bounded_text"
    assert weekly["minimum"] == 38.0
    assert weekly["maximum"] == 38.0
    assert payload["fields"]["work_model"]["value"] == "hybrid"

    display = payload["display_context"]
    assert display["experience_min_months"] == 24.0
    assert display["experience_max_months"] == 36.0
    assert display["experience_requirement_status"] == "observed_bounded_text"
    assert display["compensation"] == {
        "amount": 59417.0,
        "currency": "EUR",
        "period": "year",
        "qualifier": "minimum",
    }
    assert display["compensation_status"] == "observed_bounded_text"
    assert display["collective_agreement"] is True
    assert display["collective_agreement_status"] == "observed_bounded_text"
    assert display["observer_authority"] is False


def test_reachable_generic_surface_classifies_unstated_fields_as_source_absent() -> None:
    raw = _raw_job()
    raw["raw_data"]["job"].pop("skills")
    raw["raw_data"]["job"]["metadata"] = {}
    raw["raw_data"]["detail_evidence"].update(
        {
            "skills": [],
            "remote": None,
            "employment_types": [],
            "description_excerpt": "Wir suchen Verstärkung für unser Data-Team.",
            "description_source": "trafilatura",
            "requirement_text_excerpt": "Wir suchen Verstärkung für unser Data-Team.",
            "requirement_text_source": "trafilatura",
        }
    )
    payload = build_silver_requirement_evidence(raw)

    assert {
        field["status"] for field in payload["fields"].values()
    } == {"source_absent"}


def test_reachable_page_without_generic_requirement_surface_is_extractor_gap() -> None:
    raw = _raw_job()
    raw["raw_data"]["job"].pop("skills")
    raw["raw_data"]["job"]["metadata"] = {}
    raw["raw_data"]["detail_evidence"] = {
        "schema": "generic_job_detail_evidence_v1",
        "methods": [],
        "parser_family": "generic_dom_text",
        "structured_jobposting_found": False,
        "description_excerpt": None,
        "description_source": None,
        "requirement_text_excerpt": None,
        "requirement_text_source": None,
        "main_text_excerpt": None,
        "visible_text_excerpt": None,
        "employment_types": [],
        "skills": [],
        "remote": None,
        "raw_html_persisted": False,
    }
    payload = build_silver_requirement_evidence(raw)

    assert {
        field["status"] for field in payload["fields"].values()
    } == {"extractor_gap"}


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


def test_missing_bronze_detail_is_explicit_extractor_gap() -> None:
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
        assert field["status"] == "extractor_gap"


def test_migration_is_schema_only_bounded_sidecar() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()

    assert "create table if not exists silver_job_requirement_evidence" in sql
    assert "silver_job_id bigint primary key" in sql
    assert "evidence_payload jsonb not null" in sql
    assert "raw_html_persisted" in sql
    assert "insert into silver_job_requirement_evidence" not in sql
    assert "update silver_jobs" not in sql
