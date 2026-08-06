from __future__ import annotations

import pytest

from scripts.run_employer_origin_connector_artifact_generator import (
    SourceCandidate,
)
from src.search_intelligence.connector_artifact_query_runtime import (
    accepted_detail_urls,
    bounded_query_job_detail_url,
    build_query_aware_implementation,
    rejected_detail_urls,
    validate_query_aware_gate,
)


def candidate(origin_url: str) -> SourceCandidate:
    return SourceCandidate(
        id=57,
        company_key="example",
        company_name="Example GmbH",
        candidate_url=origin_url,
        source_name_candidate="example:discovery",
        source_family_candidate="example",
        source_target_candidate=None,
        source_type_candidate="employer_origin_career_site",
        status="discovery",
        risk_level="unknown",
    )


def gate(*urls: str) -> dict[str, object]:
    return {
        "gate_name": "connector_candidate_gate",
        "gate_status": "passed",
        "decision": "build_connector_candidate",
        "evidence": {
            "connector_candidate_spec": {
                "detail_evidence": {"detail_urls": list(urls)}
            }
        },
    }


def test_bounded_query_detail_reuses_s7n_url_safety_contract() -> None:
    origin = "https://careers.example.com/de"

    assert bounded_query_job_detail_url(
        origin_url=origin,
        candidate_url="https://careers.example.com/de?id=51980f",
    )
    assert not bounded_query_job_detail_url(
        origin_url=origin,
        candidate_url="https://careers.example.com/de?utm_source=newsletter",
    )
    assert not bounded_query_job_detail_url(
        origin_url=origin,
        candidate_url=(
            "https://careers.example.com/de"
            "?id=51980f&redirectUrl=https%3A%2F%2Fevil.test"
        ),
    )
    assert not bounded_query_job_detail_url(
        origin_url=origin,
        candidate_url="https://careers.example.com/de?id=",
    )
    assert not bounded_query_job_detail_url(
        origin_url=origin,
        candidate_url=f"https://careers.example.com/de?id={'a' * 129}",
    )
    assert not bounded_query_job_detail_url(
        origin_url=origin,
        candidate_url="https://careers.evil.test/de?id=51980f",
    )
    assert not bounded_query_job_detail_url(
        origin_url=origin,
        candidate_url="https://careers.example.com/de",
    )


def test_query_and_path_details_are_preserved_without_noise() -> None:
    source = candidate("https://careers.example.com/de")
    query_detail = "https://careers.example.com/de?id=51980f"
    path_detail = (
        "https://careers.example.com/job/"
        "Berlin-Data-Engineer/1402370533/"
    )
    tracking = "https://careers.example.com/de?utm_source=newsletter"
    redirect = (
        "https://careers.example.com/de"
        "?id=51980f&redirect=https%3A%2F%2Fevil.test"
    )
    root = "https://careers.example.com/de"
    reviewed_gate = gate(query_detail, path_detail, tracking, redirect, root)
    spec = reviewed_gate["evidence"]["connector_candidate_spec"]

    assert accepted_detail_urls(candidate=source, spec=spec) == (
        query_detail,
        path_detail,
    )
    assert rejected_detail_urls(candidate=source, spec=spec) == (
        tracking,
        redirect,
        root,
    )


def test_query_only_gate_renders_known_detail_urls_in_memory() -> None:
    source = candidate("https://careers.example.com/de")
    query_detail = "https://careers.example.com/de?id=51980f"
    reviewed_gate = gate(query_detail)

    validate_query_aware_gate(source, reviewed_gate)
    implementation = build_query_aware_implementation(
        source,
        reviewed_gate,
    )

    assert implementation.module_path.as_posix() == "src/connectors/example.py"
    assert (
        f"KNOWN_DETAIL_URLS = ({query_detail!r},)"
        in implementation.module_content
    )
    assert query_detail in implementation.docs_content
    assert "no concrete job-detail URLs" not in implementation.docs_content


def test_query_aware_gate_rejects_only_generic_or_noise_urls() -> None:
    source = candidate("https://careers.example.com/de")

    with pytest.raises(ValueError, match="does not contain concrete"):
        validate_query_aware_gate(
            source,
            gate(
                "https://careers.example.com/de",
                "https://careers.example.com/de?utm_source=newsletter",
            ),
        )
