from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterator

from src.search_intelligence.candidate_fact_authoring_pack import (
    build_empty_draft_profile,
    build_eon_authoring_workbook,
)
from src.search_intelligence.candidate_fact_guided_authoring import (
    SAVE_CONFIRMATION,
    load_private_authoring_payloads,
    run_guided_authoring_session,
    save_private_authoring_payloads,
)
from src.search_intelligence.candidate_fact_profile import parse_candidate_fact_profile


class ScriptedInput:
    def __init__(self, values: list[str]) -> None:
        self._values: Iterator[str] = iter(values)

    def __call__(self, _prompt: str) -> str:
        return next(self._values)


def _profile() -> dict[str, object]:
    return build_empty_draft_profile(profile_version="eon-authoring-draft-v1")


def _workbook() -> dict[str, object]:
    return build_eon_authoring_workbook(profile_version="eon-authoring-draft-v1")


def _fixed_now() -> datetime:
    return datetime(2026, 8, 5, 13, 30, tzinfo=timezone.utc)


def _no_evidence_answers() -> list[str]:
    answers: list[str] = []
    for _ in range(8):
        answers.extend(["2", ""])
    answers.append(SAVE_CONFIRMATION)
    return answers


def test_quit_leaves_original_payloads_unchanged() -> None:
    profile = _profile()
    workbook = _workbook()
    output: list[str] = []

    result = run_guided_authoring_session(
        profile_payload=profile,
        workbook_payload=workbook,
        input_fn=ScriptedInput(["q"]),
        output_fn=output.append,
        now_fn=_fixed_now,
    )

    assert result.quit_without_save is True
    assert result.save_confirmed is False
    assert result.changed is False
    assert result.profile_payload == profile
    assert result.workbook_payload == workbook
    assert result.integrity.decision_counts == {"unreviewed": 8}
    assert any("unverändert" in line for line in output)


def test_all_no_evidence_decisions_are_structurally_complete() -> None:
    result = run_guided_authoring_session(
        profile_payload=_profile(),
        workbook_payload=_workbook(),
        input_fn=ScriptedInput(_no_evidence_answers()),
        output_fn=lambda _line: None,
        now_fn=_fixed_now,
    )

    assert result.quit_without_save is False
    assert result.save_confirmed is True
    assert result.changed is True
    assert result.integrity.profile_fact_count == 0
    assert result.integrity.decision_counts == {"no_evidence": 8}
    assert result.integrity.authoring_complete is True
    assert result.workbook_payload["candidate_truth_state"] == "operator_reviewed"


def test_operator_can_author_proposed_portfolio_fact_without_inference() -> None:
    answers = [
        "1",  # requirement 1: evidence available
        "2",  # create new fact
        "portfolio.python.pipeline",
        "3",  # portfolio_implementation
        "1",  # project
        "Operator-authored private portfolio statement.",
        "technology.python",
        "portfolio_not_professional_production",
        "6",  # repository provenance
        "private repository reference",
        "",  # observed_at = now
        "",  # no more provenance
        "",  # valid_from
        "",  # valid_until
        "JA",
        "",  # private note unchanged
    ]
    for _ in range(7):
        answers.extend(["2", ""])
    answers.append(SAVE_CONFIRMATION)

    output: list[str] = []
    result = run_guided_authoring_session(
        profile_payload=_profile(),
        workbook_payload=_workbook(),
        input_fn=ScriptedInput(answers),
        output_fn=output.append,
        now_fn=_fixed_now,
    )

    profile = parse_candidate_fact_profile(result.profile_payload)
    assert len(profile.facts) == 1
    fact = profile.facts[0]
    assert fact.fact_key == "portfolio.python.pipeline"
    assert fact.evidence_class == "portfolio_implementation"
    assert fact.approval_status == "proposed"
    assert fact.approved_by is None
    assert fact.approved_at is None
    assert fact.statement == "Operator-authored private portfolio statement."
    assert fact.provenance[0].source_type == "repository"
    assert result.integrity.decision_counts == {
        "evidence_available": 1,
        "no_evidence": 7,
    }
    assert result.integrity.authoring_complete is True

    summary_text = json.dumps(result.redacted_summary(), ensure_ascii=False)
    assert "Operator-authored private portfolio statement" not in summary_text
    assert "private repository reference" not in summary_text
    assert "technology.python" not in summary_text
    assert "Operator-authored private portfolio statement" not in "\n".join(output)
    assert "private repository reference" not in "\n".join(output)


def test_declined_final_save_keeps_session_unsaved() -> None:
    answers = _no_evidence_answers()
    answers[-1] = "nein"

    result = run_guided_authoring_session(
        profile_payload=_profile(),
        workbook_payload=_workbook(),
        input_fn=ScriptedInput(answers),
        output_fn=lambda _line: None,
        now_fn=_fixed_now,
    )

    assert result.changed is True
    assert result.save_confirmed is False
    assert result.quit_without_save is False


def test_confirmed_save_creates_backup_and_writes_consistent_pair(
    tmp_path: Path,
) -> None:
    private_dir = tmp_path / "private_candidate_facts"
    private_dir.mkdir()
    profile_path = private_dir / "candidate_fact_profile.private.json"
    workbook_path = private_dir / "eon_candidate_fact_authoring_workbook.private.json"
    original_profile = json.dumps(_profile(), indent=2, sort_keys=True) + "\n"
    original_workbook = json.dumps(_workbook(), indent=2, sort_keys=True) + "\n"
    profile_path.write_text(original_profile, encoding="utf-8")
    workbook_path.write_text(original_workbook, encoding="utf-8")

    session = run_guided_authoring_session(
        profile_payload=_profile(),
        workbook_payload=_workbook(),
        input_fn=ScriptedInput(_no_evidence_answers()),
        output_fn=lambda _line: None,
        now_fn=_fixed_now,
    )
    saved = save_private_authoring_payloads(
        profile_path=profile_path,
        workbook_path=workbook_path,
        profile_payload=session.profile_payload,
        workbook_payload=session.workbook_payload,
        now_fn=_fixed_now,
    )

    assert saved.backup_dir.name == "20260805T133000000000Z"
    assert (saved.backup_dir / profile_path.name).read_text(
        encoding="utf-8"
    ) == original_profile
    assert (saved.backup_dir / workbook_path.name).read_text(
        encoding="utf-8"
    ) == original_workbook

    _, written_workbook, integrity = load_private_authoring_payloads(
        profile_path=profile_path,
        workbook_path=workbook_path,
    )
    assert written_workbook["candidate_truth_state"] == "operator_reviewed"
    assert integrity.authoring_complete is True
    assert integrity.decision_counts == {"no_evidence": 8}


def test_cli_has_no_database_network_import_apply_or_fit_authority() -> None:
    source = Path("scripts/author_private_candidate_facts.py").read_text(
        encoding="utf-8"
    ).casefold()

    assert "psycopg" not in source
    assert "import requests" not in source
    assert "from requests" not in source
    assert "get_database_config" not in source
    assert "--apply" not in source
    assert "approval-token" not in source
    assert "insert into" not in source
    assert "delete from" not in source
    assert 'print("candidate_fact_import_performed: false")' in source
    assert 'print("candidate_fact_approval_performed: false")' in source
    assert 'print("capability_fit_decision_created: false")' in source
