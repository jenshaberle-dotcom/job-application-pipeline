from __future__ import annotations

from scripts.run_f4a_requirement_evidence_refresh import (
    ASSESSMENT_COLUMNS,
    _build_next_payload,
    _stable_requirement_evidence_fingerprint,
)
from src.search_intelligence.product_v1_requirement_evidence import (
    extract_product_v1_requirement_evidence,
)


SOURCE_URL = "https://example.com/jobs/42"


def _html(*, skills: str = "Python, SQL") -> str:
    return f"""
    <html><head><title>Senior Data Engineer</title>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "JobPosting",
      "title": "Senior Data Engineer",
      "skills": "{skills}",
      "jobLocationType": "TELECOMMUTE"
    }}
    </script></head><body>Senior Data Engineer {skills} TELECOMMUTE</body></html>
    """


def _evidence(*, prefix: str = "", skills: str = "Python, SQL"):
    text = f"{prefix}Senior Data Engineer Requirements: {skills}. TELECOMMUTE"
    return extract_product_v1_requirement_evidence(
        html=_html(skills=skills),
        text=text,
        title="Senior Data Engineer",
        page_title="Senior Data Engineer",
        source_url=SOURCE_URL,
    )


def _blank_assessment_row() -> dict[str, object]:
    row = {column: None for column in ASSESSMENT_COLUMNS}
    row.update(
        {
            "silver_job_id": 42,
            "origin_validation_status": "validated",
            "activity_status": "active",
            "ranking_factors": {},
            "explanations": [],
            "uncertainties": [],
            "required_languages": [],
        }
    )
    return row


def test_stable_fingerprint_ignores_only_representation_drift() -> None:
    left = {
        "source_url": SOURCE_URL,
        "description_sha256": "aaa",
        "resolved_assessment_patch": {"work_model": "remote"},
        "references": [
            {
                "field": "skills",
                "source_url": SOURCE_URL,
                "evidence": "Python",
                "value": "Python",
                "span_start": 10,
                "span_end": 16,
            },
            {
                "field": "skills",
                "source_url": SOURCE_URL,
                "evidence": "SQL",
                "value": "SQL",
                "span_start": 20,
                "span_end": 23,
            },
        ],
    }
    right = {
        "source_url": SOURCE_URL,
        "description_sha256": "bbb",
        "resolved_assessment_patch": {"work_model": "remote"},
        "references": [
            {
                "field": "skills",
                "source_url": SOURCE_URL,
                "evidence": "SQL",
                "value": "SQL",
                "span_start": 120,
                "span_end": 123,
            },
            {
                "field": "skills",
                "source_url": SOURCE_URL,
                "evidence": "Python",
                "value": "Python",
                "span_start": 110,
                "span_end": 116,
            },
        ],
    }

    assert _stable_requirement_evidence_fingerprint(left) == (
        _stable_requirement_evidence_fingerprint(right)
    )


def test_stable_fingerprint_preserves_semantic_and_source_truth() -> None:
    baseline = {
        "source_url": SOURCE_URL,
        "job_skills": ["Python", "SQL"],
        "resolved_assessment_patch": {"work_model": "remote"},
        "semantic_references": [
            {
                "field": "skills",
                "source_url": SOURCE_URL,
                "evidence": "Python",
                "value": "Python",
                "span_start": 1,
                "span_end": 7,
            }
        ],
    }
    changed_skill = {
        **baseline,
        "job_skills": ["Python", "SQL", "Terraform"],
    }
    changed_source = {
        **baseline,
        "source_url": "https://example.com/jobs/99",
    }
    changed_evidence = {
        **baseline,
        "semantic_references": [
            {
                "field": "skills",
                "source_url": SOURCE_URL,
                "evidence": "Terraform",
                "value": "Terraform",
                "span_start": 1,
                "span_end": 10,
            }
        ],
    }

    baseline_fingerprint = _stable_requirement_evidence_fingerprint(baseline)
    assert _stable_requirement_evidence_fingerprint(changed_skill) != baseline_fingerprint
    assert _stable_requirement_evidence_fingerprint(changed_source) != baseline_fingerprint
    assert _stable_requirement_evidence_fingerprint(changed_evidence) != baseline_fingerprint


def test_build_next_payload_preserves_stored_raw_evidence_for_layout_only_drift() -> None:
    first = _evidence()
    initial = _build_next_payload(
        _blank_assessment_row(),
        evidence=first,
        final_url=SOURCE_URL,
    )
    stored_evidence = initial["ranking_factors"]["requirement_evidence"]
    stored_explanations = initial["explanations"]

    shifted = _evidence(prefix="Welcome to our careers page. ")
    assert first.assessment.description_sha256 != shifted.assessment.description_sha256
    assert _stable_requirement_evidence_fingerprint(first.canonical_payload()) == (
        _stable_requirement_evidence_fingerprint(shifted.canonical_payload())
    )

    refreshed = _build_next_payload(
        initial,
        evidence=shifted,
        final_url=SOURCE_URL,
    )

    assert refreshed == initial
    assert refreshed["ranking_factors"]["requirement_evidence"] == stored_evidence
    assert refreshed["explanations"] == stored_explanations


def test_build_next_payload_keeps_real_skill_change_actionable() -> None:
    first = _evidence()
    initial = _build_next_payload(
        _blank_assessment_row(),
        evidence=first,
        final_url=SOURCE_URL,
    )

    changed = _evidence(skills="Python, SQL, Terraform")
    assert _stable_requirement_evidence_fingerprint(first.canonical_payload()) != (
        _stable_requirement_evidence_fingerprint(changed.canonical_payload())
    )

    refreshed = _build_next_payload(
        initial,
        evidence=changed,
        final_url=SOURCE_URL,
    )

    assert refreshed != initial
    assert refreshed["ranking_factors"]["requirement_evidence"] != (
        initial["ranking_factors"]["requirement_evidence"]
    )
