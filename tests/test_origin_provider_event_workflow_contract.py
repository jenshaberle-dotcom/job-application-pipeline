from pathlib import Path

REUSABLE = Path(".github/workflows/reusable-origin-provider-benchmark.yml").read_text(
    encoding="utf-8"
)
CALLER = Path("docs/runtime/private_origin_runtime_caller.example.yml").read_text(
    encoding="utf-8"
)
DISPATCHER = Path("scripts/dispatch_origin_provider_benchmark_if_changed.py").read_text(
    encoding="utf-8"
)
RUNNER = Path("scripts/run_origin_provider_event_benchmark.py").read_text(
    encoding="utf-8"
)
SQL = Path("db/ops/create_origin_benchmark_reader.sql").read_text(encoding="utf-8")


def test_public_reusable_workflow_has_no_direct_or_automatic_trigger() -> None:
    assert "workflow_call:" in REUSABLE
    assert "pull_request:" not in REUSABLE
    assert "push:" not in REUSABLE
    assert "workflow_dispatch:" not in REUSABLE
    assert "schedule:" not in REUSABLE


def test_reusable_workflow_uses_ephemeral_tailscale_identity_and_private_artifact() -> None:
    assert "tailscale/github-action@v4" in REUSABLE
    assert "id-token: write" in REUSABLE
    assert "audience: ${{ secrets.ts_audience }}" in REUSABLE
    assert "ping: ${{ secrets.postgres_host }}" in REUSABLE
    assert "retention-days: 3" in REUSABLE
    assert "review_output_only_not_pipeline_input" in REUSABLE


def test_private_caller_is_event_driven_and_validates_exact_payload() -> None:
    assert "repository_dispatch:" in CALLER
    assert "origin-provider-benchmark-requested" in CALLER
    assert "invalid repository_dispatch field set" in CALLER
    assert "pipeline_ref must be an exact commit SHA" in CALLER
    assert "workflow_dispatch:" not in CALLER
    assert "schedule:" not in CALLER


def test_dispatcher_sends_only_metadata_after_change_detection() -> None:
    assert "projection_fingerprint" in DISPATCHER
    assert "unchanged projection; no event sent" in DISPATCHER
    assert '"gh",' in DISPATCHER
    assert "repos/{runtime_repository}/dispatches" in DISPATCHER
    assert "candidate_url" not in DISPATCHER
    assert "market_evidence_urls" not in DISPATCHER


def test_remote_runner_stops_on_stale_fingerprint_before_provider_loop() -> None:
    stale_position = RUNNER.index("stale_dispatch_fingerprint")
    provider_loop_position = RUNNER.index("for company_key in company_keys")
    assert stale_position < provider_loop_position
    assert "max_provider_requests" in RUNNER
    assert "review_output_only_not_pipeline_input" in RUNNER


def test_database_role_is_read_only_and_table_scoped() -> None:
    assert "default_transaction_read_only = 'on'" in SQL
    assert "employer_origin_source_candidates" in SQL
    assert "market_evidence" in SQL
    assert "GRANT SELECT ON TABLE" in SQL
    assert "GRANT INSERT" not in SQL
    assert "GRANT UPDATE" not in SQL
    assert "GRANT DELETE" not in SQL
