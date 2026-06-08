from __future__ import annotations

import pytest

from scripts.run_employer_origin_connector_implementation_agent import (
    SourceCandidate,
    build_implementation,
    class_name_for,
    module_name_for,
    snake_case,
    validate_gate,
)


def make_candidate(source_type: str = "employer_origin_career_site") -> SourceCandidate:
    return SourceCandidate(
        id=2,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/jobs",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        source_target_candidate="hannover",
        source_type_candidate=source_type,
        status="connector_candidate",
        risk_level="low",
    )


def make_gate(status: str = "passed", decision: str = "build_connector_candidate") -> dict:
    return {
        "gate_name": "connector_candidate_gate",
        "gate_status": status,
        "decision": decision,
        "evidence": {
            "connector_candidate_spec": {
                "detail_evidence": {
                    "detail_urls": [
                        "https://careers.hdi.group/jobs/product-owner-data-platform",
                    ]
                }
            }
        },
    }


def test_name_helpers_create_expected_paths_and_class_names() -> None:
    assert snake_case("Finanz Informatik") == "finanz_informatik"
    assert module_name_for(make_candidate()) == "hdi"
    assert class_name_for(make_candidate()) == "HdiConnector"


def test_validate_gate_requires_passed_connector_candidate_gate() -> None:
    with pytest.raises(ValueError, match="not passed"):
        validate_gate(make_candidate(), make_gate(status="manual_review_required"))


def test_validate_gate_requires_connector_candidate_spec() -> None:
    gate = make_gate()
    gate["evidence"] = {}

    with pytest.raises(ValueError, match="connector_candidate_spec"):
        validate_gate(make_candidate(), gate)


def test_build_implementation_writes_candidate_files_without_activation() -> None:
    implementation = build_implementation(make_candidate(), make_gate())

    assert str(implementation.module_path) == "src/connectors/hdi.py"
    assert str(implementation.test_path) == "tests/test_hdi_connector.py"
    assert str(implementation.docs_path) == "docs/planning/active/source-candidates/hdi_connector_candidate.md"

    assert "class HdiConnector" in implementation.module_content
    assert "SOURCE_NAME = 'hdi:hannover'" in implementation.module_content
    assert "SOURCE_TYPE = 'employer_origin_career_site'" in implementation.module_content
    assert "browser_automation_used" in implementation.module_content
    assert "raw_html_persisted" in implementation.module_content
    assert "Generated from DB-backed approval-gated connector evidence" in implementation.docs_content
    assert "does not approve" in implementation.docs_content

def test_validate_gate_rejects_overview_and_legal_urls_as_detail_evidence() -> None:
    gate = make_gate()
    gate["evidence"]["connector_candidate_spec"]["detail_evidence"]["detail_urls"] = [
        "https://careers.hdi.group/de/karriere/jobs",
        "https://careers.hdi.group/en/privacy",
    ]

    with pytest.raises(ValueError, match="concrete job-detail URLs"):
        validate_gate(make_candidate(), gate)

def test_gate_stop_lines_are_user_readable_without_traceback_language() -> None:
    from scripts.run_employer_origin_connector_implementation_agent import gate_stop_lines

    lines = gate_stop_lines(
        make_candidate(),
        "connector_candidate_gate is not passed/build_connector_candidate for hdi: manual_review_required / manual_review_required",
    )

    text = "\\n".join(lines)
    assert "candidate_id: 2" in text
    assert "candidate: hdi | hdi:hannover" in text
    assert "STOP:" in text
    assert "No connector artifact files were written." in text
    assert "Traceback" not in text
