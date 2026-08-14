from __future__ import annotations

from types import SimpleNamespace

import scripts.run_detail_discovery_booster as cli
from scripts.run_employer_origin_detail_evidence_repair_agent import (
    DetailEvidence,
    RepairOutcome,
)

ORIGIN = "https://jobs.example.com/"
DETAIL = "https://jobs.example.com/jobs/123-data-engineer"


def args(*extra: str):  # type: ignore[no-untyped-def]
    return cli.build_parser().parse_args(
        [
            "--candidate-id",
            "42",
            "--company-key",
            "example",
            "--company-name",
            "Example GmbH",
            "--candidate-url",
            ORIGIN,
            *extra,
        ]
    )


def d0_outcome(*, resolved: bool, candidate_found: bool = False) -> RepairOutcome:
    candidates = [{"url": DETAIL, "reason": "fixture"}] if candidate_found else []
    assessments = (
        [
            {
                "url": DETAIL,
                "decision": "manual_review_required",
                "failure_reason": "detail_page_extracted_but_no_target_signal",
            }
        ]
        if candidate_found and not resolved
        else []
    )
    supported = (
        [
            {
                "url": DETAIL,
                "final_url": DETAIL,
                "status_code": 200,
                "profile_terms": ["data"],
                "location_terms": ["hannover"],
            }
        ]
        if resolved
        else []
    )
    details = (
        (
            DetailEvidence(
                url=DETAIL,
                final_url=DETAIL,
                status_code=200,
                title="Data Engineer",
                profile_terms=("data",),
                location_terms=("hannover",),
                html_bytes=100,
                reason="fixture",
            ),
        )
        if resolved
        else ()
    )
    return RepairOutcome(
        gate_status="passed" if resolved else "manual_review_required",
        decision="passed" if resolved else "manual_review_required",
        stop_reason=None if resolved else "fixture unresolved",
        details=details,
        rejected_urls=(),
        requested_urls=(ORIGIN,),
        evidence={
            "repair_attempted": True,
            "search_discovery_enabled": False,
            "detail_link_discovery_version": "DETAIL-004B",
            "detail_url_shape_version": "fixture-v1",
            "decision_taxonomy": "accepted" if resolved else "manual_review_required",
            "preliminary_detail_candidates": candidates,
            "authoritative_detail_assessments": assessments,
            "supported_detail_evidence": supported,
            "checked_origin_candidates": [
                {
                    "url": ORIGIN,
                    "final_url": ORIGIN,
                    "status": (
                        "job_detail_candidates_found"
                        if candidate_found or resolved
                        else "checked_no_detail_candidates"
                    ),
                    "status_code": 200,
                    "rejection_reasons": [],
                }
            ],
        },
    )


def test_command_forces_provider_free_d0_and_has_no_write_boundary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def fake_d0(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)
        return d0_outcome(resolved=True)

    monkeypatch.setattr(cli, "build_repair_outcome", fake_d0)
    payload = cli.run(args("--disable-tavily", "--disable-llm"))

    assert captured["enable_search_discovery"] is False
    assert captured["max_search_queries"] == 0
    assert payload["execution"]["resolved"] is True  # type: ignore[index]
    boundary = payload["boundary"]
    assert boundary["database_requests"] == 0  # type: ignore[index]
    assert boundary["database_writes"] == 0  # type: ignore[index]
    assert boundary["detail_gate_write"] is False  # type: ignore[index]
    assert boundary["product_writes"] == 0  # type: ignore[index]
    assert boundary["product_authority"] is False  # type: ignore[index]


def test_tavily_url_cannot_resolve_when_deterministic_validator_rejects(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        cli,
        "build_repair_outcome",
        lambda **kwargs: d0_outcome(resolved=False),
    )
    monkeypatch.setattr(
        cli,
        "web_search",
        lambda *args, **kwargs: [SimpleNamespace(url=DETAIL)],
    )
    monkeypatch.setattr(
        cli,
        "validate_detail_candidates",
        lambda **kwargs: (
            (),
            (f"{DETAIL} :: detail_page_extracted_but_no_target_signal",),
            (DETAIL,),
            (
                {
                    "url": DETAIL,
                    "decision": "manual_review_required",
                    "failure_reason": "detail_page_extracted_but_no_target_signal",
                },
            ),
        ),
    )

    payload = cli.run(
        args(
            "--tavily-remaining-credits",
            "2",
            "--disable-llm",
        )
    )

    execution = payload["execution"]
    assert execution["resolved"] is False  # type: ignore[index]
    assert execution["provider_requests"] == 1  # type: ignore[index]
    assert execution["llm_requests"] == 0  # type: ignore[index]
    assert execution["product_writes"] == 0  # type: ignore[index]
    assert execution["product_authority"] is False  # type: ignore[index]


def test_tavily_url_resolves_only_after_existing_validator_accepts(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setattr(
        cli,
        "build_repair_outcome",
        lambda **kwargs: d0_outcome(resolved=False),
    )
    monkeypatch.setattr(
        cli,
        "web_search",
        lambda *args, **kwargs: [SimpleNamespace(url=DETAIL)],
    )
    accepted = DetailEvidence(
        url=DETAIL,
        final_url=DETAIL,
        status_code=200,
        title="Data Engineer",
        profile_terms=("data",),
        location_terms=("hannover",),
        html_bytes=123,
        reason="fixture accepted",
    )
    monkeypatch.setattr(
        cli,
        "validate_detail_candidates",
        lambda **kwargs: ((accepted,), (), (DETAIL,), ()),
    )

    payload = cli.run(
        args(
            "--tavily-remaining-credits",
            "2",
            "--disable-llm",
        )
    )

    execution = payload["execution"]
    assert execution["resolved"] is True  # type: ignore[index]
    assert execution["resolved_url"] == DETAIL  # type: ignore[index]
    assert execution["provider_requests"] == 1  # type: ignore[index]
    validation = execution["resolved_validation"]  # type: ignore[index]
    assert validation["accepted"] is True
    assert validation["product_authority"] is False


def test_candidate_validation_gap_passes_d0_failure_evidence_to_model(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    captured: list[tuple[dict[str, object], ...]] = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        cli,
        "build_repair_outcome",
        lambda **kwargs: d0_outcome(resolved=False, candidate_found=True),
    )

    def fake_model(**kwargs):  # type: ignore[no-untyped-def]
        captured.append(tuple(dict(item) for item in kwargs["attempted_candidate_summaries"]))
        return cli.DetailDiscoveryHypothesisObservation(
            status="completed",
            request_attempted=True,
            urls=(),
            model=kwargs["model"],
            estimated_cost_usd=0.001,
        )

    monkeypatch.setattr(cli, "request_detail_discovery_hypotheses", fake_model)
    payload = cli.run(args("--disable-tavily"))

    assert captured
    first = captured[0]
    assert any(
        item.get("url") == DETAIL
        and item.get("failure_reason") == "detail_page_extracted_but_no_target_signal"
        for item in first
    )
    stages = payload["execution"]["stages"]  # type: ignore[index]
    tavily = next(item for item in stages if item["stage"] == "tavily")
    assert tavily["attempted"] is False
    assert payload["boundary"]["detail_gate_write"] is False  # type: ignore[index]
