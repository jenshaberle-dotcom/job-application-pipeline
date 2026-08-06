"""Query-aware projection for approval-gated connector artifacts.

The historical artifact generator remains authoritative for path-based job-detail
URLs and artifact rendering. This adapter adds only URL-shape validation for
query-parameter job details already accepted by the active S7N runtime.
"""

from __future__ import annotations

from unittest.mock import patch
from typing import Any

from scripts import run_employer_origin_connector_artifact_generator as generator
from src.search_intelligence.connector_feasibility_query_runtime import (
    _safe_query_job_detail_link,
)


QUERY_DETAIL_EVIDENCE_LABEL = "Data Engineer"


def bounded_query_job_detail_url(*, origin_url: str, candidate_url: str) -> bool:
    """Validate a query-detail URL through the active S7N safety contract.

    The persisted feasibility item already carries role-label evidence. The
    synthetic generic role label therefore supplies only the label precondition
    while all host, path, identifier, scope, tracking and redirect checks remain
    owned by S7N.
    """

    return _safe_query_job_detail_link(
        origin_url=origin_url,
        candidate_url=candidate_url,
        label=QUERY_DETAIL_EVIDENCE_LABEL,
    )


def accepted_detail_urls(
    *,
    candidate: generator.SourceCandidate,
    spec: dict[str, Any],
) -> tuple[str, ...]:
    detail = spec.get("detail_evidence") or {}
    urls = detail.get("detail_urls") or []
    return generator.safe_tuple(
        [
            str(url)
            for url in urls
            if str(url).startswith(("http://", "https://"))
            and (
                generator.concrete_job_detail_url(str(url))
                or bounded_query_job_detail_url(
                    origin_url=candidate.candidate_url,
                    candidate_url=str(url),
                )
            )
        ]
    )


def rejected_detail_urls(
    *,
    candidate: generator.SourceCandidate,
    spec: dict[str, Any],
) -> tuple[str, ...]:
    detail = spec.get("detail_evidence") or {}
    urls = detail.get("detail_urls") or []
    accepted = set(accepted_detail_urls(candidate=candidate, spec=spec))
    return generator.safe_tuple(
        [
            str(url)
            for url in urls
            if str(url).startswith(("http://", "https://"))
            and str(url) not in accepted
        ]
    )


def validate_query_aware_gate(
    candidate: generator.SourceCandidate,
    gate: dict[str, Any] | None,
) -> None:
    if gate is None:
        raise ValueError(
            f"Missing {generator.REQUIRED_GATE} for candidate "
            f"{candidate.company_key}."
        )

    if (
        gate.get("gate_status") != "passed"
        or gate.get("decision") != "build_connector_candidate"
    ):
        raise ValueError(
            f"{generator.REQUIRED_GATE} is not "
            f"passed/build_connector_candidate for {candidate.company_key}: "
            f"{gate.get('gate_status')} / {gate.get('decision')}"
        )

    spec = generator.extract_spec_from_gate(gate)
    if not spec:
        raise ValueError(
            f"{generator.REQUIRED_GATE} does not contain "
            "connector_candidate_spec evidence."
        )

    if not accepted_detail_urls(candidate=candidate, spec=spec):
        rejected = rejected_detail_urls(candidate=candidate, spec=spec)
        raise ValueError(
            f"{generator.REQUIRED_GATE} connector_candidate_spec does not "
            "contain concrete job-detail URLs. "
            f"Rejected URLs: {list(rejected)}"
        )


def build_query_aware_implementation(
    candidate: generator.SourceCandidate,
    gate: dict[str, Any],
) -> generator.ConnectorImplementation:
    """Render the existing artifact templates with query details preserved."""

    spec = generator.extract_spec_from_gate(gate)
    module_name = generator.module_name_for(candidate)
    accepted = accepted_detail_urls(candidate=candidate, spec=spec)
    rejected = rejected_detail_urls(candidate=candidate, spec=spec)

    with (
        patch.object(
            generator,
            "extract_detail_urls_from_spec",
            return_value=accepted,
        ),
        patch.object(
            generator,
            "rejected_detail_urls_from_spec",
            return_value=rejected,
        ),
    ):
        module_content = generator.connector_module_content(
            candidate=candidate,
            spec=spec,
        )
        docs_content = generator.connector_docs_content(candidate, spec)

    return generator.ConnectorImplementation(
        module_path=generator.Path("src/connectors") / f"{module_name}.py",
        test_path=generator.Path("tests") / f"test_{module_name}_connector.py",
        docs_path=(
            generator.Path("docs/planning/active/source-candidates")
            / f"{module_name}_connector_candidate.md"
        ),
        module_content=module_content,
        test_content=generator.connector_test_content(candidate),
        docs_content=docs_content,
    )
