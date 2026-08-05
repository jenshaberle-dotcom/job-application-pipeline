from __future__ import annotations

from pathlib import Path

from src.search_intelligence.eon_requirement_heading_diagnostic import (
    DIAGNOSTIC_SCHEMA,
    build_heading_diagnostics,
    diagnostic_payload,
)


RUNNER = Path("scripts/run_eon_requirement_heading_diagnostic.py").read_text(
    encoding="utf-8"
)


def test_reports_exact_nonbreaking_hyphen_codepoint() -> None:
    description = (
        "<h2>Your Role – meaningful & rewarding</h2>"
        "<p>Build operational data-driven solutions.</p>"
        "<h2>Your Profile – authentic & open‑minded\u200b</h2>"
        "<p>Extensive professional experience in data engineering.</p>"
    )

    candidates = build_heading_diagnostics(description)
    profile = next(item for item in candidates if "Your Profile" in item.text)

    assert profile.ascii_repr == "'Your Profile \\u2013 authentic & open\\u2011minded'"
    assert [item.codepoint for item in profile.non_ascii_characters] == [
        "U+2013",
        "U+2011",
    ]
    assert [item.name for item in profile.non_ascii_characters] == [
        "EN DASH",
        "NON-BREAKING HYPHEN",
    ]
    assert [item.category for item in profile.non_ascii_characters] == ["Pd", "Pd"]


def test_format_characters_are_removed_before_diagnostic_output() -> None:
    description = "<h2>Your Profile\u200b – authentic & open-minded\ufeff</h2>"

    candidate = build_heading_diagnostics(description)[0]

    assert "\\u200b" not in candidate.ascii_repr
    assert "\\ufeff" not in candidate.ascii_repr
    assert all(item.category != "Cf" for item in candidate.non_ascii_characters)


def test_diagnostic_includes_bounded_heading_like_lines_only() -> None:
    description = (
        "<p>This is a long introductory sentence that ends with a period.</p>"
        "<h2>Your Role – meaningful & rewarding</h2>"
        "<p>Build operational data-driven solutions.</p>"
        "<h2>Your Profile – authentic & open-minded</h2>"
        "<p>Extensive professional experience in data engineering.</p>"
        "<h2>Our Benefits – smart & useful</h2>"
    )

    candidates = build_heading_diagnostics(description)
    texts = [item.text for item in candidates]

    assert "Your Role – meaningful & rewarding" in texts
    assert "Your Profile – authentic & open-minded" in texts
    assert "Our Benefits – smart & useful" in texts
    assert "Build operational data-driven solutions." not in texts
    assert "Extensive professional experience in data engineering." not in texts


def test_diagnostic_payload_is_review_only_and_nonmutating() -> None:
    payload = diagnostic_payload(
        "<h2>Your Profile – authentic & open‑minded</h2>"
    )

    assert payload["schema_version"] == DIAGNOSTIC_SCHEMA
    assert payload["review_output_only_not_pipeline_input"] is True
    assert payload["candidate_count"] == 1
    assert payload["boundaries"] == {
        "database_writes": 0,
        "candidate_fact_reads": 0,
        "candidate_fact_writes": 0,
        "capability_fit_decision_created": False,
        "assessment_mutation": False,
        "readiness_mutation": False,
        "network_requests": 0,
        "provider_requests": 0,
        "source_or_scheduler_activation": False,
        "application_action_performed": False,
    }


def test_runner_is_exact_job_bound_and_read_only() -> None:
    assert "EXPECTED_RAW_JOB_ID" in RUNNER
    assert "EXPECTED_SILVER_JOB_ID" in RUNNER
    assert 'cur.execute("SET TRANSACTION READ ONLY")' in RUNNER
    assert "load_exact_eon_binding(" in RUNNER
    assert 'print("database_writes: 0")' in RUNNER
    assert 'print("candidate_fact_reads: 0")' in RUNNER
    assert 'print("capability_fit_decision_created: false")' in RUNNER
    assert "INSERT INTO" not in RUNNER
    assert "UPDATE " not in RUNNER
    assert "DELETE FROM" not in RUNNER
    assert "requests.get" not in RUNNER
    assert "requests.post" not in RUNNER


def test_runner_emits_ascii_repr_and_named_unicode_codepoints() -> None:
    assert "candidate['ascii_repr']" in RUNNER
    assert "item['codepoint']" in RUNNER
    assert "item['name']" in RUNNER
    assert "item['category']" in RUNNER
    assert "eon_requirement_heading_diagnostic_" in RUNNER
