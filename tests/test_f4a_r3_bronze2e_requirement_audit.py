from scripts.run_f4a_r3_bronze2e_requirement_audit import build_report


def _row(*, assessment: bool) -> dict[str, object]:
    return {
        "silver_job_id": 10,
        "raw_job_id": 20,
        "source_name": "generic_origin:example",
        "source_url": "https://jobs.example.test/10",
        "title": "Data Engineer",
        "company_name": "Example GmbH",
        "raw_data": {
            "job": {
                "title": "Data Engineer",
                "source_url": "https://jobs.example.test/10",
                "skills": ["Python", "SQL"],
            },
            "detail_evidence": {
                "schema": "generic_job_detail_evidence_v1",
                "parser_family": "schema_org_json_ld",
                "methods": ["extruct:json-ld"],
                "structured_jobposting_found": True,
                "skills": ["Python", "SQL"],
                "remote": True,
                "description_excerpt": "Sehr gute Deutschkenntnisse auf C1-Niveau.",
            },
        },
        "normalized_evidence": None,
        "employment_type": "unknown",
        "required_languages": ["de"] if assessment else [],
        "weekly_hours_min": None,
        "weekly_hours_max": None,
        "work_model": "remote" if assessment else "unknown",
        "requirements_seniority": "unknown",
        "product_requirement_evidence": {"job_skills": ["Python", "SQL"]} if assessment else {},
    }


def test_audit_distinguishes_preserved_from_bronze_loss() -> None:
    preserved = build_report([_row(assessment=True)])
    lost = build_report([_row(assessment=False)])

    assert preserved["field_classification_counts"]["job_skills"] == {
        "preserved_or_rederived": 1
    }
    assert preserved["field_classification_counts"]["required_languages"] == {
        "preserved_or_rederived": 1
    }

    assert lost["field_classification_counts"]["job_skills"] == {
        "bronze_truth_lost_before_product": 1
    }
    assert lost["field_classification_counts"]["required_languages"] == {
        "bronze_truth_lost_before_product": 1
    }
    assert lost["rows_with_bronze_truth_lost_before_product"] == 1


def test_audit_boundaries_are_read_only_and_authority_free() -> None:
    report = build_report([_row(assessment=True)])

    assert report["boundaries"] == {
        "database_writes": 0,
        "provider_calls": 0,
        "candidate_fact_reads": 0,
        "ranking_authority": 0,
        "top5_authority": 0,
        "application_authority": 0,
        "raw_html_persisted": 0,
    }
