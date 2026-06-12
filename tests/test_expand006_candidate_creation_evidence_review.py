from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_expand006_candidate_creation_evidence_review.py"
spec = importlib.util.spec_from_file_location("expand006_review", MODULE_PATH)
assert spec is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)


def test_safety_boundary_is_review_only() -> None:
    assert module.SAFETY_BOUNDARY["read_only"] is True
    assert module.SAFETY_BOUNDARY["database_writes"] is False
    assert module.SAFETY_BOUNDARY["candidate_or_gate_mutation"] is False
    assert module.SAFETY_BOUNDARY["connector_activation"] is False
    assert module.SAFETY_BOUNDARY["scheduler_change"] is False


def test_build_report_without_db_keeps_apply_blocked(tmp_path: Path) -> None:
    report = module.build_report(tmp_path, include_db=False, database_url=None, sample_limit=3)

    assert report["schema_version"] == module.SCHEMA_VERSION
    assert report["database"]["status"] == "skipped"
    assert report["apply_boundary"]["decision_boundary"] == "review_only_not_apply"
    assert report["apply_boundary"]["candidate_creation_allowed_by_this_report"] is False
    assert report["next_safe_action"]["requires_user_decision"] is True


def test_markdown_mentions_boundaries(tmp_path: Path) -> None:
    report = module.build_report(tmp_path, include_db=False, database_url=None, sample_limit=0)
    markdown = module.render_markdown(report)

    assert "EXPAND-006 Candidate Creation Evidence Review" in markdown
    assert "review_only_not_apply" in markdown
    assert "candidate_or_gate_mutation" in markdown
    assert "This report is intentionally not an apply mechanism" in markdown


def test_quote_ident_rejects_unsafe_identifier() -> None:
    assert module.quote_ident("valid_identifier_123") == '"valid_identifier_123"'

    try:
        module.quote_ident("invalid-name")
    except ValueError as exc:
        assert "Unsafe SQL identifier" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected unsafe identifier to be rejected")
