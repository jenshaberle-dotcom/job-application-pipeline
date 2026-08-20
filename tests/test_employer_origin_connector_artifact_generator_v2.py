from __future__ import annotations

from scripts import run_employer_origin_connector_artifact_generator as legacy
from scripts.run_employer_origin_connector_artifact_generator_v2 import (
    GENERATOR_SEMANTICS,
    connector_module_content_v2,
    connector_test_content_v2,
    validate_gate_v2,
)


def make_candidate(*, candidate_url: str = "https://jobs.example.test/careers") -> legacy.SourceCandidate:
    return legacy.SourceCandidate(
        id=99,
        company_key="example",
        company_name="Example GmbH",
        candidate_url=candidate_url,
        source_name_candidate="example:discovery",
        source_family_candidate="example",
        source_target_candidate="hannover",
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="medium",
    )


def passed_gate(*, detail_urls: list[str] | None = None) -> dict:
    return {
        "gate_status": "passed",
        "decision": "build_connector_candidate",
        "evidence": {
            "connector_candidate_spec": {
                "detail_evidence": {"detail_urls": detail_urls or []},
            },
        },
    }


def test_v2_gate_requires_valid_origin_but_not_prequalified_detail_url() -> None:
    validate_gate_v2(make_candidate(), passed_gate(detail_urls=[]))


def test_v2_generator_defers_relevance_and_uses_shared_acquisition_helper() -> None:
    candidate = make_candidate()
    module = connector_module_content_v2(candidate=candidate, spec={"detail_evidence": {"detail_urls": []}})

    compile(module, "<generated-connector>", "exec")
    assert GENERATOR_SEMANTICS == "employer_origin_acquisition_first.v2"
    assert "acquire_genuine_job_pages" in module
    assert '"relevance_gated": False' in module
    assert '"qualification_deferred": True' in module
    assert "PROFILE_TERMS" not in module
    assert "TARGET_LOCATION_TERMS" not in module
    assert "detail_supports_record" not in module
    assert "max_followup_requests=self.max_detail_pages" in module


def test_v2_generated_fixture_proves_irrelevant_real_job_and_rejects_privacy() -> None:
    content = connector_test_content_v2(make_candidate())

    compile(content, "<generated-connector-test>", "exec")
    assert "Backend Engineer Berlin" in content
    assert 'search_location="Hannover"' in content
    assert "PRIVACY_URL not in calls" in content
    assert "calls == [LISTING_URL, INTERMEDIATE_URL, DETAIL_URL]" in content
    assert 'record.raw_data["acquisition_boundary"]["relevance_gated"] is False' in content
