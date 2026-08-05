from __future__ import annotations

import pytest

from src.search_intelligence.eon_product_v1_source_evidence import (
    extract_eon_source_evidence,
)


def _description(requirement: str) -> str:
    return (
        f"Your Profile: {requirement}. "
        "Fluent in English and German. "
        "Enjoy hybrid work with office collaboration and focused work from home."
    )


def test_accepts_exact_stored_eon_extensive_experience_wording() -> None:
    evidence = extract_eon_source_evidence(
        description=_description(
            "Extensive professional experience in data engineering positions "
            "and a consulting background"
        ),
        title="(Senior) Data Engineer Data & AI (f/m/d)",
    )

    assert evidence.requirements_seniority == "senior"
    assert "Extensive professional experience" in evidence.seniority_evidence_text
    assert evidence.required_languages == ("de", "en")
    assert evidence.work_model == "hybrid"


def test_does_not_accept_unqualified_professional_experience() -> None:
    with pytest.raises(ValueError, match="extensive professional experience"):
        extract_eon_source_evidence(
            description=_description(
                "Professional experience in data engineering positions"
            ),
            title="(Senior) Data Engineer Data & AI (f/m/d)",
        )


def test_extensive_evidence_does_not_create_numeric_years_or_capability_fit() -> None:
    evidence = extract_eon_source_evidence(
        description=_description(
            "Extensive professional experience in data engineering positions"
        ),
        title="(Senior) Data Engineer Data & AI (f/m/d)",
    )

    payload = evidence.canonical_payload()
    assert payload["requirements_seniority"] == "senior"
    assert "years" not in payload
    assert "capability_fit_status" not in payload
