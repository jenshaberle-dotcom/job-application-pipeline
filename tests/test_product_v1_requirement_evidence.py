from __future__ import annotations

from src.search_intelligence.product_v1_requirement_evidence import (
    extract_product_v1_requirement_evidence,
)


def _html(*, skills: str = "Python, SQL", location_type: str = "TELECOMMUTE") -> str:
    return f"""
    <html><head><title>Senior Data Engineer</title>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "Senior Data Engineer",
      "skills": "{skills}",
      "jobLocationType": "{location_type}"
    }}
    </script></head><body>
    <h1>Senior Data Engineer</h1>
    <section>Requirements: Python and SQL.</section>
    <section>TELECOMMUTE</section>
    </body></html>
    """


def test_structured_skills_and_contextual_remote_fill_are_job_evidence_only() -> None:
    evidence = extract_product_v1_requirement_evidence(
        html=_html(),
        text="Requirements: Python and SQL. TELECOMMUTE",
        title="Senior Data Engineer",
        page_title="Senior Data Engineer",
        source_url="https://example.com/jobs/1",
    )

    assert evidence.assessment.work_model == "unknown"
    assert evidence.semantic_work_model == "remote"
    assert evidence.work_model == "remote"
    assert evidence.work_model_resolution == "contextual_fill"
    assert evidence.job_skills == ("Python", "SQL")
    assert evidence.assessment.requirements_seniority == "unknown"
    assert evidence.assessment.title_seniority == "senior"
    assert "work_model" not in evidence.unresolved_fields

    payload = evidence.canonical_payload()
    assert payload["authority"]["candidate_fact_authority"] is False
    assert payload["authority"]["capability_fit_authority"] is False
    assert payload["authority"]["requirements_seniority_from_title"] is False
    assert payload["authority"]["ranking_authority"] is False


def test_contradictory_flat_and_contextual_work_model_fails_closed() -> None:
    evidence = extract_product_v1_requirement_evidence(
        html=_html(),
        text="This is an onsite role. Requirements: Python and SQL. TELECOMMUTE",
        title="Senior Data Engineer",
        page_title="Senior Data Engineer",
        source_url="https://example.com/jobs/2",
    )

    assert evidence.assessment.work_model == "onsite"
    assert evidence.semantic_work_model == "remote"
    assert evidence.work_model == "unknown"
    assert evidence.work_model_resolution == "conflict_unknown"
    assert "work_model" in evidence.conflicted_fields
    assert "work_model" in evidence.unresolved_fields


def test_semantic_seniority_never_becomes_requirements_seniority() -> None:
    evidence = extract_product_v1_requirement_evidence(
        html=_html(skills="Python"),
        text="Requirements: Python. TELECOMMUTE",
        title="Senior Data Engineer",
        page_title="Senior Data Engineer",
        source_url="https://example.com/jobs/3",
    )

    patch = evidence.assessment_patch()
    assert patch["title_seniority"] == "senior"
    assert patch["requirements_seniority"] == "unknown"
    assert patch["seniority_evidence_status"] == "unknown"
