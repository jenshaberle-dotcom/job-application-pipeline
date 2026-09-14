from __future__ import annotations

import json

from src.connectors.generic_job_detail_evidence import (
    extract_generic_job_detail_evidence,
    project_detail_evidence_into_raw_data,
)


def _jobposting(**values: object) -> str:
    posting: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Machine Learning Engineer",
        "description": "Build production machine-learning systems with Python.",
        **values,
    }
    return (
        '<html><head><script type="application/ld+json">'
        + json.dumps(posting)
        + "</script></head><body></body></html>"
    )


def test_schema_work_hours_are_preserved_and_feed_bounded_requirement_text() -> None:
    evidence = extract_generic_job_detail_evidence(
        html=_jobposting(employmentType="FULL_TIME", workHours="40 hours per week"),
        url="https://jobs.example.test/ml-1",
    )

    assert evidence["employment_types"] == ["FULL_TIME"]
    assert evidence["work_hours"] == "40 hours per week"
    assert evidence["field_presence"]["work_hours"] is True
    assert "Work hours: 40 hours per week" in evidence["requirement_text_excerpt"]

    projected = project_detail_evidence_into_raw_data({"job": {}}, evidence)
    assert projected["job"]["metadata"]["work_hours"] == "40 hours per week"


def test_structured_experience_months_are_preserved_without_level_inference() -> None:
    evidence = extract_generic_job_detail_evidence(
        html=_jobposting(
            experienceRequirements={
                "@type": "OccupationalExperienceRequirements",
                "monthsOfExperience": "36",
            }
        ),
        url="https://jobs.example.test/ml-2",
    )

    assert evidence["experience_months"] == 36.0
    assert evidence["experience_requirement"] == "36 months experience"
    assert evidence["field_presence"]["experience_requirement"] is True
    assert "36 months experience" in evidence["requirement_text_excerpt"]

    projected = project_detail_evidence_into_raw_data({"job": {}}, evidence)
    assert projected["job"]["metadata"]["experience_months"] == 36.0
    assert projected["job"]["metadata"]["experience_requirement"] == "36 months experience"
