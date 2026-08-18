from __future__ import annotations

from argparse import Namespace

from scripts.product_v1_downstream_preview_runtime import (
    DownstreamEvidenceMaterialization,
)
from scripts import run_product_v1_ai_booster_campaign as campaign


DETAIL = "Join our data platform team. Build data pipelines with SQL."


def _materialization(detail_text: str = DETAIL) -> DownstreamEvidenceMaterialization:
    return DownstreamEvidenceMaterialization(
        row={
            "silver_job_id": 42,
            "title": "Data Engineer",
            "company_name": "Example GmbH",
            "source_url": "https://jobs.example.com/42",
            "canonical_source_type": "employer_origin",
            "origin_validation_status": "validated",
            "activity_status": "active",
            "product_readiness_status": "hard_filter_decision_required",
        },
        final_url="https://jobs.example.com/42",
        fetched_title="Data Engineer | Example GmbH",
        detail_text=detail_text,
    )


def _args(
    *,
    surface: str = "assessment",
    previous: tuple[str, ...] = (),
    execute: bool = False,
) -> Namespace:
    return Namespace(
        silver_job_id=42,
        surface=surface,
        previous_terminal_fingerprint=list(previous),
        execute_provider_booster=execute,
        output=None,
    )


def test_campaign_is_provider_free_by_default_and_emits_replay_identity(monkeypatch) -> None:
    monkeypatch.setattr(
        campaign,
        "load_downstream_evidence_materialization",
        lambda _job_id: _materialization(),
    )

    payload = campaign.run(_args())

    assert payload["outcome"] == "provider_execution_disabled"
    assert payload["surface"] == "assessment"
    assert payload["unresolved_scope"]
    assert payload["replay_preflight"]["provider_eligible"] is True
    assert len(payload["replay_preflight"]["input_fingerprint"]) == 64
    assert payload["provider_requests"] == 0
    assert payload["llm_requests"] == 0
    assert payload["database_writes"] == 0
    assert payload["product_writes"] == 0
    assert payload["product_authority"] is False
    assert payload["terminal_replay_reusable"] is False


def test_exact_previous_terminal_fingerprint_skips_before_provider_callback(monkeypatch) -> None:
    monkeypatch.setattr(
        campaign,
        "load_downstream_evidence_materialization",
        lambda _job_id: _materialization(),
    )
    first = campaign.run(_args())
    fingerprint = first["replay_preflight"]["input_fingerprint"]

    def unexpected_provider_callback(**_kwargs):
        raise AssertionError("unchanged terminal replay must stop before provider callback")

    monkeypatch.setattr(
        campaign,
        "openai_assessment_model_callback",
        unexpected_provider_callback,
    )
    payload = campaign.run(
        _args(previous=(fingerprint,), execute=True)
    )

    assert payload["outcome"] == "unchanged_terminal_replay_skipped"
    assert payload["replay_preflight"]["replay_suppressed"] is True
    assert payload["provider_requests"] == 0
    assert payload["llm_requests"] == 0
    assert payload["terminal_replay_reusable"] is True
    assert payload["terminal_fingerprint"] == fingerprint


def test_provider_opt_in_still_fails_closed_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        campaign,
        "load_downstream_evidence_materialization",
        lambda _job_id: _materialization(),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    payload = campaign.run(_args(execute=True))

    assert payload["outcome"] == "provider_configuration_blocked"
    assert payload["provider_requests"] == 0
    assert payload["terminal_replay_reusable"] is False
    assert payload["terminal_fingerprint"] is None


def test_ranking_campaign_uses_same_replay_guard_and_stays_provider_free(monkeypatch) -> None:
    monkeypatch.setattr(
        campaign,
        "load_downstream_evidence_materialization",
        lambda _job_id: _materialization(),
    )

    payload = campaign.run(_args(surface="ranking"))

    assert payload["outcome"] == "provider_execution_disabled"
    assert payload["surface"] == "ranking"
    assert payload["unresolved_scope"]
    assert payload["replay_preflight"]["provider_eligible"] is True
    assert payload["provider_requests"] == 0
    assert payload["ranking_writes"] == 0
    assert payload["top5_writes"] == 0
    assert payload["ranking_authority"] is False
    assert payload["top5_authority"] is False


def test_shared_materialization_keeps_existing_preview_loader_behavior(monkeypatch) -> None:
    from scripts import product_v1_downstream_preview_runtime as runtime

    calls: list[str] = []
    row = dict(_materialization().row)
    monkeypatch.setattr(
        runtime,
        "_load_preview_job",
        lambda job_id: calls.append(f"db:{job_id}") or row,
    )
    monkeypatch.setattr(
        runtime,
        "fetch_public_https_detail_text",
        lambda url: calls.append(f"detail:{url}")
        or (url, "Data Engineer", DETAIL),
    )

    materialization = runtime.load_downstream_evidence_materialization(42)
    preview = runtime.load_downstream_evidence_preview_payload(42)

    assert materialization.row["silver_job_id"] == 42
    assert preview["status"] == "preview_ready"
    assert preview["boundaries"]["provider_requests"] == 0
    assert preview["boundaries"]["database_writes"] == 0
    assert calls == [
        "db:42",
        "detail:https://jobs.example.com/42",
        "db:42",
        "detail:https://jobs.example.com/42",
    ]
