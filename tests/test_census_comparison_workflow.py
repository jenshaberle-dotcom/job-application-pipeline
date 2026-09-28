from pathlib import Path


WORKFLOW = Path(".github/workflows/freeze2-job-first-census-comparison.yml")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_census_comparison_workflow_defaults_to_zero_provider_requests():
    text = _text()
    assert "default: none" in text
    assert "allow_paid_external_provider:" in text
    assert "default: false" in text


def test_census_comparison_workflow_requires_explicit_paid_provider_gate():
    text = _text()
    assert "Enforce paid-provider double gate" in text
    assert 'if [[ "$ALLOW_PAID_EXTERNAL_PROVIDER" != "true" ]]' in text
    assert "--allow-paid-external-provider" in text


def test_census_comparison_workflow_uses_read_only_runtime_and_no_board_credentials():
    text = _text()
    assert 'PGOPTIONS="-c default_transaction_read_only=on"' in text
    assert "TAVILY_API_KEY" in text
    for forbidden in (
        "XING_PASSWORD",
        "XING_COOKIE",
        "GOODJOBS_PASSWORD",
        "MEINESTADT_PASSWORD",
        "JOBVECTOR_PASSWORD",
        "GET_IN_IT_PASSWORD",
    ):
        assert forbidden not in text


def test_census_comparison_workflow_is_freezable_before_blue_runner_assignment():
    text = _text()
    lines = text.splitlines()
    blue_index = next(
        i for i, line in enumerate(lines)
        if "runs-on:" in line and "job-pipeline-runtime-linux" in line
    )
    assert any(
        "RCC_JAP_BLUE_ASSIGNMENT_FROZEN" in line
        for line in lines[:blue_index]
    )


def test_census_comparison_issue_trigger_is_owner_only_and_issue_scoped():
    text = _text()
    assert "issue_comment:" in text
    assert "github.event.issue.number == 1066" in text
    assert "github.event.comment.user.login == 'jenshaberle-dotcom'" in text
    assert "github.event.comment.author_association == 'OWNER'" in text
    assert "<!-- jap-freeze2-census-comparison:run:v1 -->" in text


def test_issue_trigger_requires_explicit_provider_paid_choice_and_cost_budget():
    text = _text()
    assert "Resolve explicit flight request" in text
    assert "provider=(tavily|none)" in text
    assert "allow_paid=(true|false)" in text
    assert "max_requests=([0-9]+)" in text
    assert 'allow_paid="false"' in text
    assert 'max_requests="50"' in text


def test_workflow_has_no_hidden_term_location_or_profile_truncation():
    text = _text()
    for forbidden in (
        "--max-terms",
        "--max-locations",
        "--radius-km",
        "--page-size",
    ):
        assert forbidden not in text

    assert "--max-external-requests" in text
    assert "full raster is never truncated" in text
    assert "planned external-index queries" in text
