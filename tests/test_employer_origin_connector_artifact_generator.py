from __future__ import annotations

from scripts.run_employer_origin_connector_artifact_generator import (
    SourceCandidate,
    build_implementation,
)


def test_artifact_generator_uses_candidate_doc_path_and_approval_gated_wording() -> None:
    candidate = SourceCandidate(
        id=2,
        company_key="hdi",
        company_name="HDI Group",
        candidate_url="https://careers.hdi.group/jobs",
        source_name_candidate="hdi:hannover",
        source_family_candidate="hdi",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="connector_candidate",
        risk_level="low",
    )
    gate = {
        "gate_name": "connector_candidate_gate",
        "gate_status": "passed",
        "decision": "build_connector_candidate",
        "evidence": {
            "connector_candidate_spec": {
                "detail_evidence": {
                    "detail_urls": ["https://careers.hdi.group/jobs/product-owner-data-platform"]
                }
            }
        },
    }

    implementation = build_implementation(candidate, gate)

    assert str(implementation.docs_path) == "docs/source_analysis/hdi_connector_candidate.md"
    assert "Generated from DB-backed approval-gated connector evidence" in implementation.docs_content
    assert "does not approve" in implementation.docs_content
