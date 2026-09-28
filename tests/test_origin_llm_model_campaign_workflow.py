from pathlib import Path


RUNNER = Path("scripts/run_origin_llm_model_campaign.py")


def test_diagnostic_runner_writes_artifacts_before_nonzero_exit() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    write_report = text.index("_write_json_atomic(args.output, report)")
    write_diagnostics = text.index("if args.diagnostics_output is not None:")
    diagnostic_failure = text.index("if args.diagnostic_mode and failed_count:")
    assert write_report < write_diagnostics < diagnostic_failure
    assert "diagnostic mode requires exactly one case, one model and one request" in text
    assert "return 2" in text
