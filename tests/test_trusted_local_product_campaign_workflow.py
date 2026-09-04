from pathlib import Path


WORKFLOW = Path(".github/workflows/trusted-local-product-campaign.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_untrusted_request_admission_does_not_consume_local_runner() -> None:
    text = _workflow_text()
    admission = text.index("\n  admission:\n")
    campaign = text.index("\n  campaign:\n")

    assert admission < campaign
    assert "runs-on: ubuntu-latest" in text[admission:campaign]
    assert 'gh api "repos/$GITHUB_REPOSITORY/commits/main"' in text[admission:campaign]
    assert 'if [[ "$GITHUB_SHA" != "$current_main_sha" ]]' in text[admission:campaign]
    assert "job-pipeline-runtime-linux" not in text[admission:campaign]


def test_only_admitted_request_reaches_exact_local_product_runner() -> None:
    text = _workflow_text()
    campaign = text.index("\n  campaign:\n")
    execution = text[campaign:]

    assert "needs: admission" in execution
    assert "if: needs.admission.outputs.admitted == 'true'" in execution
    assert "runs-on: [self-hosted, Linux, X64, job-pipeline-runtime-linux]" in execution
    assert "TRUSTED_MAIN_SHA: ${{ needs.admission.outputs.trusted_main_sha }}" in execution
    assert 'if [[ "$actual_sha" != "$TRUSTED_MAIN_SHA" ]]' in execution
    assert "ubuntu-latest" not in execution


def test_only_db_execution_is_serialized_not_hosted_admission() -> None:
    text = _workflow_text()
    admission = text.index("\n  admission:\n")
    campaign = text.index("\n  campaign:\n")

    assert "\nconcurrency:" not in text
    assert "concurrency:" not in text[admission:campaign]
    assert "group: trusted-local-product-campaign" in text[campaign:]
    assert "cancel-in-progress: false" in text[campaign:]
