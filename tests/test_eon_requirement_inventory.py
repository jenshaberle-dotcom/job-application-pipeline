from __future__ import annotations

from pathlib import Path

import pytest

from src.search_intelligence.eon_requirement_inventory import (
    INVENTORY_KEY,
    build_eon_requirement_inventory,
    classify_requirement_family,
    description_lines,
)


TITLE = "(Senior) Data Engineer Data & AI (f/m/d)"
RUNNER = Path("scripts/run_eon_requirement_inventory.py").read_text(
    encoding="utf-8"
)


def _description(*, formatting: str = "list") -> str:
    profile_statements = [
        "A university degree in a relevant discipline.",
        (
            "Extensive professional experience in data engineering positions "
            "and a consulting background."
        ),
        "Strong technical knowledge of cloud data platforms and data pipelines.",
        "Fluent in English and German.",
        "Collaborative communication with business stakeholders and agile teams.",
        "Curiosity and a pragmatic mindset.",
    ]
    if formatting == "list":
        profile = "<ul>" + "".join(
            f"<li>{statement}</li>" for statement in profile_statements
        ) + "</ul>"
    elif formatting == "paragraphs":
        profile = "".join(
            f"<div><p> {statement} </p></div>" for statement in profile_statements
        )
    else:
        raise AssertionError(formatting)

    return (
        "<h2>Your Tasks</h2>"
        "<p>Build products that must not enter the profile inventory.</p>"
        "<h2>Your Profile</h2>"
        f"{profile}"
        "<h2>What we offer</h2>"
        "<p>Attractive benefits that must not enter the profile inventory.</p>"
    )


def test_builds_ordered_requirement_inventory_from_profile_section() -> None:
    inventory = build_eon_requirement_inventory(
        description=_description(),
        title=TITLE,
    )

    assert inventory.inventory_key == INVENTORY_KEY
    assert inventory.section_heading == "Your Profile"
    assert len(inventory.statements) == 6
    assert [statement.order for statement in inventory.statements] == [1, 2, 3, 4, 5, 6]
    assert [statement.family for statement in inventory.statements] == [
        "education",
        "experience",
        "technical_capability",
        "language",
        "collaboration",
        "unclassified",
    ]
    assert all(statement.statement_key.startswith("eon-req-") for statement in inventory.statements)
    assert len({statement.statement_key for statement in inventory.statements}) == 6


def test_excludes_tasks_benefits_and_application_marketing() -> None:
    inventory = build_eon_requirement_inventory(
        description=_description(),
        title=TITLE,
    )
    text = "\n".join(statement.text for statement in inventory.statements)

    assert "Build products" not in text
    assert "Attractive benefits" not in text
    assert "Your Tasks" not in text
    assert "What we offer" not in text


def test_statement_keys_and_section_hash_ignore_irrelevant_html_formatting() -> None:
    list_inventory = build_eon_requirement_inventory(
        description=_description(formatting="list"),
        title=TITLE,
    )
    paragraph_inventory = build_eon_requirement_inventory(
        description=_description(formatting="paragraphs"),
        title=TITLE,
    )

    assert [item.text for item in list_inventory.statements] == [
        item.text for item in paragraph_inventory.statements
    ]
    assert [item.statement_key for item in list_inventory.statements] == [
        item.statement_key for item in paragraph_inventory.statements
    ]
    assert list_inventory.section_sha256 == paragraph_inventory.section_sha256
    assert list_inventory.description_sha256 != paragraph_inventory.description_sha256


def test_supports_heading_and_first_statement_on_same_line() -> None:
    description = (
        "<p>Your Profile: Extensive professional experience in data engineering.</p>"
        "<p>Fluent in English and German.</p>"
        "<p>What we offer</p>"
        "<p>Benefits</p>"
    )

    inventory = build_eon_requirement_inventory(
        description=description,
        title=TITLE,
    )

    assert inventory.section_heading == "Your Profile"
    assert len(inventory.statements) == 2
    assert inventory.statements[0].family == "experience"
    assert inventory.statements[1].family == "language"


def test_deduplicates_repeated_requirement_blocks() -> None:
    description = (
        "<h2>Your Profile</h2>"
        "<p>Extensive professional experience in data engineering.</p>"
        "<p>Extensive professional experience in data engineering.</p>"
        "<p>Fluent in English and German.</p>"
        "<p>What we offer</p>"
    )

    inventory = build_eon_requirement_inventory(
        description=description,
        title=TITLE,
    )

    assert len(inventory.statements) == 2


def test_unknown_requirement_remains_unclassified() -> None:
    assert classify_requirement_family("Curiosity and a pragmatic mindset.") == "unclassified"


def test_classification_uses_explicit_statement_signals() -> None:
    assert classify_requirement_family("Fluent in English and German.") == "language"
    assert classify_requirement_family("A university degree is required.") == "education"
    assert classify_requirement_family("Extensive professional experience.") == "experience"
    assert classify_requirement_family("Strong knowledge of Python and SQL.") == "technical_capability"
    assert classify_requirement_family("Work with business stakeholders.") == "collaboration"


def test_description_lines_preserve_block_order_and_remove_bullet_prefixes() -> None:
    lines = description_lines(
        "<h2>Your Profile</h2><ul><li>• Fluent in English and German.</li>"
        "<li>2. Extensive professional experience.</li></ul>"
    )

    assert lines == (
        "Your Profile",
        "Fluent in English and German.",
        "Extensive professional experience.",
    )


def test_fails_closed_without_profile_section() -> None:
    description = (
        "<h2>Requirements overview</h2>"
        "<p>Extensive professional experience.</p>"
        "<p>Fluent in English and German.</p>"
    )

    with pytest.raises(ValueError, match="no recognized profile section"):
        build_eon_requirement_inventory(description=description, title=TITLE)


def test_fails_closed_when_language_is_outside_profile_section() -> None:
    description = (
        "<p>Fluent in English and German.</p>"
        "<h2>Your Profile</h2>"
        "<p>Extensive professional experience in data engineering.</p>"
        "<h2>What we offer</h2>"
    )

    with pytest.raises(
        ValueError,
        match="does not explicitly evidence fluent German and English",
    ):
        build_eon_requirement_inventory(description=description, title=TITLE)


def test_fails_closed_when_experience_is_outside_profile_section() -> None:
    description = (
        "<p>Extensive professional experience in data engineering.</p>"
        "<h2>Your Profile</h2>"
        "<p>Fluent in English and German.</p>"
        "<h2>What we offer</h2>"
    )

    with pytest.raises(
        ValueError,
        match="does not explicitly evidence extensive professional experience",
    ):
        build_eon_requirement_inventory(description=description, title=TITLE)


def test_fails_closed_when_existing_source_evidence_is_missing() -> None:
    description = (
        "<h2>Your Profile</h2>"
        "<p>Some professional experience in data engineering.</p>"
        "<p>Knowledge of English and German.</p>"
        "<h2>What we offer</h2>"
    )

    with pytest.raises(ValueError, match="fluent German and English"):
        build_eon_requirement_inventory(description=description, title=TITLE)


def test_runner_is_strictly_read_only_and_exact_job_bound() -> None:
    assert "EXPECTED_RAW_JOB_ID = 26342" in RUNNER
    assert "EXPECTED_SILVER_JOB_ID = 466" in RUNNER
    assert 'cur.execute("SET TRANSACTION READ ONLY")' in RUNNER
    assert "bind_eon_job(" in RUNNER
    assert '"database_writes": 0' in RUNNER
    assert '"candidate_fact_reads": 0' in RUNNER
    assert '"candidate_fact_writes": 0' in RUNNER
    assert '"capability_fit_decision_created": False' in RUNNER
    assert '"assessment_mutation": False' in RUNNER
    assert '"readiness_mutation": False' in RUNNER
    assert '"ranking_scores_created": False' in RUNNER
    assert '"weekly_hours_inferred": False' in RUNNER
    assert '"network_requests": 0' in RUNNER
    assert '"provider_requests": 0' in RUNNER
    assert '"source_or_scheduler_activation": False' in RUNNER
    assert '"application_action_performed": False' in RUNNER
    assert "INSERT INTO" not in RUNNER
    assert "UPDATE job_product_assessments" not in RUNNER
    assert "candidate_facts" not in RUNNER


def test_runner_report_is_review_only_and_preserves_employer_statements() -> None:
    assert '"review_output_only_not_pipeline_input": True' in RUNNER
    assert '"inventory": inventory.canonical_payload()' in RUNNER
    assert "statement.text" in RUNNER
    assert "statement.statement_key" in RUNNER
