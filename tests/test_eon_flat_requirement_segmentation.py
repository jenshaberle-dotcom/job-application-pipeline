from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from scripts.run_eon_requirement_inventory import build_inventory_from_binding
from src.search_intelligence.eon_flat_requirement_segmentation import (
    END_HEADING,
    EXACT_PROFILE_STATEMENTS,
    PROFILE_HEADING,
    prepare_eon_requirement_description,
)
from src.search_intelligence.eon_requirement_inventory import (
    build_eon_requirement_inventory,
)


TITLE = "(Senior) Data Engineer Data & AI (f/m/d)"
RUNNER = Path("scripts/run_eon_requirement_inventory.py").read_text(
    encoding="utf-8"
)


def _flat_page(*, profile_body: str | None = None) -> str:
    body = profile_body or " ".join(EXACT_PROFILE_STATEMENTS)
    prefix = (
        "(Senior) Data Engineer Data & AI (f/m/d) Job Details | E.ON "
        + "navigation chrome " * 70
        + "Your Role – meaningful & rewarding Build operational data-driven solutions "
    )
    suffix = (
        " Advance your development and enjoy hybrid work "
        + "application chrome " * 70
    )
    return f"{prefix}{PROFILE_HEADING} {body} {END_HEADING}{suffix}"


def test_reconstructs_exact_flattened_profile_into_eight_blocks() -> None:
    prepared = prepare_eon_requirement_description(_flat_page())
    inventory = build_eon_requirement_inventory(
        description=prepared,
        title=TITLE,
    )

    assert [statement.text for statement in inventory.statements] == list(
        EXACT_PROFILE_STATEMENTS
    )
    assert [statement.family for statement in inventory.statements] == [
        "experience",
        "experience",
        "experience",
        "technical_capability",
        "experience",
        "experience",
        "collaboration",
        "language",
    ]
    assert inventory.family_counts() == {
        "collaboration": 1,
        "experience": 5,
        "language": 1,
        "technical_capability": 1,
    }


def test_runner_preserves_original_flat_source_fingerprint() -> None:
    flat_description = _flat_page()
    inventory = build_inventory_from_binding(
        {
            "raw_data": {
                "job": {
                    "title": TITLE,
                    "description": flat_description,
                }
            }
        }
    )

    assert inventory.description_sha256 == sha256(
        flat_description.encode("utf-8")
    ).hexdigest()
    assert inventory.description_sha256 != sha256(
        str(prepare_eon_requirement_description(flat_description)).encode("utf-8")
    ).hexdigest()


def test_surrounding_page_chrome_role_and_benefits_are_excluded() -> None:
    prepared = prepare_eon_requirement_description(_flat_page())
    inventory = build_eon_requirement_inventory(description=prepared, title=TITLE)
    text = "\n".join(statement.text for statement in inventory.statements)

    assert "navigation chrome" not in text
    assert "Your Role" not in text
    assert "Build operational" not in text
    assert "Advance your development" not in text
    assert "application chrome" not in text


def test_structured_description_remains_unchanged() -> None:
    structured = (
        "<h2>Your Profile</h2>"
        "<p>Extensive professional experience in data engineering.</p>"
        "<p>Fluent in English and German.</p>"
        "<h2>What we offer</h2>"
    )

    assert prepare_eon_requirement_description(structured) == structured


def test_fails_closed_when_one_statement_is_missing() -> None:
    body = " ".join(EXACT_PROFILE_STATEMENTS[:-1])

    with pytest.raises(ValueError, match="profile body differs"):
        prepare_eon_requirement_description(_flat_page(profile_body=body))


def test_fails_closed_when_statements_are_reordered() -> None:
    reordered = (
        EXACT_PROFILE_STATEMENTS[1],
        EXACT_PROFILE_STATEMENTS[0],
        *EXACT_PROFILE_STATEMENTS[2:],
    )

    with pytest.raises(ValueError, match="profile body differs"):
        prepare_eon_requirement_description(
            _flat_page(profile_body=" ".join(reordered))
        )


def test_fails_closed_when_profile_contains_extra_text() -> None:
    body = " ".join(EXACT_PROFILE_STATEMENTS) + " Additional inferred capability"

    with pytest.raises(ValueError, match="profile body differs"):
        prepare_eon_requirement_description(_flat_page(profile_body=body))


def test_fails_closed_on_duplicate_exact_heading() -> None:
    description = _flat_page().replace(
        PROFILE_HEADING,
        f"{PROFILE_HEADING} {PROFILE_HEADING}",
        1,
    )

    with pytest.raises(ValueError, match="exact profile heading once"):
        prepare_eon_requirement_description(description)


def test_fails_closed_on_short_single_line_input() -> None:
    with pytest.raises(ValueError, match="too short"):
        prepare_eon_requirement_description(
            f"{PROFILE_HEADING} {' '.join(EXACT_PROFILE_STATEMENTS)} {END_HEADING}"
        )


def test_runner_uses_bounded_flattened_description_adapter() -> None:
    assert "prepare_eon_requirement_description" in RUNNER
    assert "prepared_description = prepare_eon_requirement_description(" in RUNNER
    assert "description=prepared_description" in RUNNER
    assert "original_description_sha256" in RUNNER
    assert 'cur.execute("SET TRANSACTION READ ONLY")' in RUNNER
    assert '"database_writes": 0' in RUNNER
    assert '"candidate_fact_reads": 0' in RUNNER
    assert '"capability_fit_decision_created": False' in RUNNER
    assert "INSERT INTO" not in RUNNER
    assert "UPDATE job_product_assessments" not in RUNNER
