from __future__ import annotations

from dataclasses import replace
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.search_intelligence import product_v1_codex_application_adapter as adapter
from src.search_intelligence.f6_template_authority import template_spec
from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)


DETAIL = (
    "AI Automation Engineer (m/w/d). accompio sucht Verstärkung für Python, "
    "PostgreSQL und AI Automation in Innsbruck."
)


def _document(document_type: str, content: str) -> ApplicationSourceDocumentSnapshot:
    return ApplicationSourceDocumentSnapshot(
        document_type=document_type,
        source_label=document_type,
        source_reference=f"local://{document_type}.pdf",
        content_sha256=template_spec(document_type).sha256,
        content=content,
        status="approved",
        source_hash_verified=True,
    )


def _context():
    return build_product_v1_application_context(
        target=ApplicationTargetSnapshot(
            silver_job_id=626,
            product_rank=None,
            title="AI Automation Engineer (m/w/d)",
            company_name="accompio",
            source_url="https://jobs.example/accompio/626",
            canonical_source_type="employer_origin",
            product_readiness_status="hard_filter_evidence_required",
            origin_validation_status="validated",
            activity_status="active",
            hard_filter_status="unknown",
            detail_text=DETAIL,
            authority_source="operator_selected_current_job",
        ),
        candidate_profile_status="approved",
        candidate_profile_sha256="c" * 64,
        candidate_facts=(
            CandidateFactSnapshot(
                fact_key="python",
                category="skill",
                evidence_class="professional_employment",
                approval_status="approved",
                statement="Python und PostgreSQL nutze ich in eigenen Data-Engineering-Projekten.",
                capability_tags=("Python", "PostgreSQL"),
                limitations=(),
            ),
        ),
        source_documents=(
            _document(
                "base_cv",
                "Jens Haberle. System Development Engineer / Product Owner. "
                "Python, PostgreSQL, Data Pipelines, ML Evaluation.",
            ),
            _document(
                "base_application_letter",
                "Hornetsecurity GmbH. Julia Klein. Sehr geehrte Frau Klein. "
                "Bewerbung als AI Automation Architect.",
            ),
        ),
        as_of_date=date(2026, 9, 24),
    )


def _model_output() -> dict[str, object]:
    return {
        "status": "draft_for_review",
        "language": "de",
        "contact_name": "",
        "salutation": "Sehr geehrte Damen und Herren,",
        "cv_short_profile": (
            "System- und Data-Engineering-Profil mit Python, PostgreSQL und "
            "praxisnaher AI-Automation."
        ),
        "cv_competency_profile": (
            "Python · PostgreSQL · Data Pipelines · ML Evaluation · System Engineering"
        ),
        "letter_paragraphs": [
            (
                "Die Position AI Automation Engineer bei accompio verbindet Python-basierte "
                "Automatisierung mit einem Umfeld, in dem ich meine System- und Data-Engineering-Erfahrung einbringen kann."
            ),
            (
                "In eigenen Data-Engineering-Projekten arbeite ich mit Python und PostgreSQL "
                "und verbinde Datenmodellierung, Pipeline-Logik und Qualitätskontrollen."
            ),
            (
                "Aus meiner beruflichen System-Engineering- und Product-Owner-Erfahrung bringe "
                "ich zusätzlich strukturierte Anforderungsarbeit, Traceability und technische Abstimmung mit."
            ),
            "Gerne erläutere ich Ihnen im Gespräch, wie ich diese Erfahrung bei accompio einbringen kann.",
        ],
        "rationale": "Auf die nachgewiesenen Python-, Daten- und System-Engineering-Bezüge fokussiert.",
    }


def test_codex_schema_carries_text_only_and_no_layout_authority() -> None:
    schema = adapter._schema()
    encoded = json.dumps(schema, sort_keys=True)

    for forbidden in (
        "bbox",
        "x",
        "y",
        "width",
        "height",
        "font_size",
        "page_count",
        "add_page",
        "remove_page",
        "move_zone",
    ):
        assert f'"{forbidden}"' not in encoded


def test_prompt_includes_current_cv_letter_and_vacancy_with_split_authority() -> None:
    prompt = adapter._prompt(_context())

    assert "System Development Engineer / Product Owner" in prompt
    assert "Hornetsecurity GmbH" in prompt
    assert "Julia Klein" in prompt
    assert '"company_name": "accompio"' in prompt
    assert '"authority": "style_structure_quality_reference_only"' in prompt
    assert '"stale_fields":' in prompt
    assert '"current_cv_and_letter_and_vacancy_are_shared_with_codex": true' in prompt
    assert '"signature_image"' in prompt
    assert '"all_pixels_outside_declared_text_zones"' in prompt
    assert '"no_scaling_or_overlay_authority": true' in prompt
    assert '"base_application_letter:recipient.block"' in prompt
    assert '"base_application_letter:body.paragraph_1..6"' in prompt
    assert '"cv_competency_profile_max_chars": 180' in prompt
    assert '"letter_paragraph_min_count": 4' in prompt
    assert '"letter_paragraph_max_count": 6' in prompt
    assert '"letter_paragraph_max_chars": 520' in prompt


def test_renderer_feedback_adds_progressive_hard_compaction_targets() -> None:
    previous = {
        "preview": {
            "cv_short_profile": "Kurzprofil",
            "cv_competency_profile": "Kompetenzen",
            "application_letter": "Absatz",
        },
        "zone_replacements": {
            "base_application_letter": {
                "body.paragraph_1": "X" * 200,
            },
        },
    }

    prompt = adapter._prompt(
        _context(),
        layout_feedback=("base_application_letter:body.paragraph_1",),
        previous_package=previous,
    )

    assert '"previous_chars": 200' in prompt
    assert '"hard_target_max_chars": 130' in prompt
    assert '"base_application_letter:body.paragraph_1"' in prompt


def test_codex_schema_freezes_current_f6_text_budgets() -> None:
    schema = adapter._schema()
    properties = schema["properties"]

    assert properties["cv_short_profile"]["maxLength"] == 520
    assert properties["cv_competency_profile"]["maxLength"] == 180
    assert properties["letter_paragraphs"]["minItems"] == 4
    assert properties["letter_paragraphs"]["maxItems"] == 6
    assert properties["letter_paragraphs"]["items"]["maxLength"] == 520


def test_embedded_codex_maps_complete_letter_identity_without_template_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapter, "_resolve_codex", lambda: "/usr/bin/codex")
    monkeypatch.setattr(adapter, "_codex_version", lambda _exe: "codex-cli 0.154.0")
    monkeypatch.setattr(adapter, "_codex_login_status", lambda _exe: (True, "Logged in using ChatGPT"))

    def fake_run(command, **kwargs):
        if command[1:] == ["--version"]:
            return SimpleNamespace(returncode=0, stdout="codex-cli 0.153.0", stderr="")
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(
            json.dumps(_model_output(), ensure_ascii=False),
            encoding="utf-8",
        )
        assert "--full-auto" not in command
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert command[command.index("--model") + 1] == "gpt-5.6-sol"
        assert 'model_reasoning_effort="high"' in command
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(adapter.subprocess, "run", fake_run)

    result = adapter.request_codex_application_adaptation(
        context=_context(),
        as_of_date=date(2026, 9, 24),
    )

    assert result.status == "completed"
    assert result.package is not None
    zones = result.package["zone_replacements"]
    letter = zones["base_application_letter"]
    assert letter["recipient.block"] == "accompio"
    assert letter["date"] == "24.09.2026"
    assert letter["subject"] == "Bewerbung als AI Automation Engineer (m/w/d)"
    assert letter["salutation"] == "Sehr geehrte Damen und Herren,"
    combined = "\n".join(letter.values())
    assert "Hornetsecurity" not in combined
    assert "Julia Klein" not in combined
    assert zones["base_cv"]["p1.short_profile"]
    assert zones["base_cv"]["p1.competency_profile"]
    assert zones["base_cv"]["p2.footer.date"] == "Hannover, 24. September 2026"
    assert result.reasoning_effort == "high"


def test_codex_capacity_exhaustion_returns_no_low_quality_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapter, "_resolve_codex", lambda: "/usr/bin/codex")
    monkeypatch.setattr(adapter, "_codex_version", lambda _exe: "codex-cli 0.154.0")
    monkeypatch.setattr(adapter, "_codex_login_status", lambda _exe: (True, "Logged in using ChatGPT"))

    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="Usage limit reached. Add credits or wait for your allowance reset.",
        ),
    )

    result = adapter.request_codex_application_adaptation(context=_context())

    assert result.status == "unavailable"
    assert result.reason_code == "codex_capacity_unavailable"
    assert result.package is None
    assert result.attempted is True


def test_missing_chatgpt_login_stops_before_model_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapter, "_resolve_codex", lambda: "/runtime/vendor/codex/codex")
    monkeypatch.setattr(adapter, "_codex_version", lambda _exe: "codex-cli 0.154.0")
    monkeypatch.setattr(
        adapter,
        "_codex_login_status",
        lambda _exe: (False, "Not logged in"),
    )

    result = adapter.request_codex_application_adaptation(context=_context())

    assert result.status == "unavailable"
    assert result.reason_code == "codex_auth_required"
    assert result.attempted is False
    assert result.package is None


def test_codex_login_status_accepts_chatgpt_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        adapter.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="Logged in using an API key - sk-...1234",
        ),
    )

    logged_in, output = adapter._codex_login_status("/runtime/vendor/codex/codex")

    assert logged_in is False
    assert "API key" in output


def test_runtime_status_reports_non_chatgpt_auth_without_enabling_drafting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapter, "_resolve_codex", lambda: "/runtime/vendor/codex/codex")
    monkeypatch.setattr(adapter, "_codex_version", lambda _exe: "codex-cli 0.154.0")
    monkeypatch.setattr(
        adapter,
        "_codex_login_status",
        lambda _exe: (False, "Logged in using an API key - sk-...1234"),
    )

    status = adapter.inspect_codex_runtime_status()

    assert status.status == "auth_required"
    assert status.installed is True
    assert status.chatgpt_authenticated is False
    assert status.auth_mode == "api_key"
    assert status.reasoning_effort == "high"
    assert status.to_json()["reasoning_effort"] == "high"
    assert status.to_json()["api_key_fallback"] is False
    assert status.to_json()["automatic_credit_purchase"] is False


def test_api_key_codex_login_is_rejected_for_jap_drafting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(adapter, "_resolve_codex", lambda: "/runtime/vendor/codex/codex")
    monkeypatch.setattr(adapter, "_codex_version", lambda _exe: "codex-cli 0.154.0")
    monkeypatch.setattr(
        adapter,
        "_codex_login_status",
        lambda _exe: (False, "Logged in using an API key - sk-...1234"),
    )

    result = adapter.request_codex_application_adaptation(context=_context())

    assert result.status == "unavailable"
    assert result.reason_code == "codex_chatgpt_auth_required"
    assert result.attempted is False
    assert result.package is None
    assert "included allowance" in (result.reason or "")


def test_codex_subprocess_environment_does_not_inherit_jap_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", "/home/jens")
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("POSTGRES_PASSWORD", "db-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "api-secret")
    monkeypatch.setenv("GITHUB_TOKEN", "github-secret")
    monkeypatch.setenv("CODEX_HOME", "/home/jens/.codex")

    environment = adapter._codex_environment()

    assert environment["HOME"] == "/home/jens"
    assert environment["PATH"] == "/usr/bin"
    assert environment["CODEX_HOME"] == "/home/jens/.codex"
    assert environment["JAP_CODEX_EMBEDDED"] == "1"
    assert "POSTGRES_PASSWORD" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert "GITHUB_TOKEN" not in environment


def test_invented_contact_is_removed_and_salutation_falls_back_safely() -> None:
    decoded = _model_output()
    decoded["contact_name"] = "Julia Klein"
    decoded["salutation"] = "Sehr geehrte Frau Klein,"

    package = adapter._validate_output(
        decoded,
        context=_context(),
        as_of_date=date(2026, 9, 24),
    )

    assert package["contact_name"] == ""
    letter = package["zone_replacements"]["base_application_letter"]
    assert letter["recipient.block"] == "accompio"
    assert letter["salutation"] == "Guten Tag,"
    assert package["automatic_semantic_repairs"] == [
        "invented_contact_removed_and_generic_salutation_used"
    ]


def test_overlong_competency_profile_is_rejected_before_review() -> None:
    decoded = _model_output()
    decoded["cv_competency_profile"] = "X" * (
        adapter.CV_COMPETENCY_PROFILE_MAX_CHARS + 1
    )

    with pytest.raises(adapter.CodexApplicationDraftStop, match="competency profile"):
        adapter._validate_output(
            decoded,
            context=_context(),
            as_of_date=date(2026, 9, 24),
        )


def test_letter_accepts_quality_range_but_rejects_more_than_six_paragraphs() -> None:
    decoded = _model_output()
    decoded["letter_paragraphs"] = list(decoded["letter_paragraphs"]) + [
        "Ein fünfter vollständiger Absatz darf bei ausreichendem Platz genutzt werden.",
        "Ein sechster vollständiger Absatz darf ebenfalls für einen sauberen Abschluss dienen.",
        "Ein siebter Absatz liegt außerhalb des freigegebenen F6-Layouts.",
    ]

    with pytest.raises(adapter.CodexApplicationDraftStop, match="quality range"):
        adapter._validate_output(
            decoded,
            context=_context(),
            as_of_date=date(2026, 9, 24),
        )


def test_unfinished_letter_paragraph_is_rejected_before_rendering() -> None:
    decoded = _model_output()
    decoded["letter_paragraphs"][2] = (
        "Aus meiner beruflichen Erfahrung bringe ich strukturierte Entscheidungen und belastbaren"
    )

    with pytest.raises(adapter.CodexApplicationDraftStop, match="unfinished"):
        adapter._validate_output(
            decoded,
            context=_context(),
            as_of_date=date(2026, 9, 24),
        )



def test_cv_short_profile_preserves_deliberate_paragraph_break() -> None:
    decoded = _model_output()
    decoded["cv_short_profile"] = (
        "Erfahrener System Engineer mit langjähriger Verantwortung für komplexe Schnittstellen.\n\n"
        "Heute verbinde ich diese Erfahrung mit Python, SQL und reproduzierbaren Datenpipelines."
    )

    package = adapter._validate_output(
        decoded,
        context=_context(),
        as_of_date=date(2026, 9, 24),
    )

    assert "\n\n" in package["preview"]["cv_short_profile"]
    assert (
        package["zone_replacements"]["base_cv"]["p1.short_profile"]
        == package["preview"]["cv_short_profile"]
    )



def test_target_specificity_accepts_company_brand_without_legal_suffix() -> None:
    base = _context()
    context = replace(
        base,
        target=replace(
            base.target,
            company_name="Finanz Informatik GmbH & Co. KG",
            title="Data Platform Engineer (m/w/d)",
        ),
    )
    decoded = _model_output()
    decoded["letter_paragraphs"] = [
        "Die Position als Data Platform Engineer bei Finanz Informatik spricht mich an, weil sie Plattform-Engineering und Datenverarbeitung verbindet.",
        *decoded["letter_paragraphs"][1:],
    ]

    package = adapter._validate_output(
        decoded,
        context=context,
        as_of_date=date(2026, 9, 24),
    )

    assert package["status"] == "draft_for_review"


def test_target_specificity_accepts_role_without_gender_marker() -> None:
    base = _context()
    context = replace(
        base,
        target=replace(
            base.target,
            company_name="Unbekannte Beispiel GmbH",
            title="Data Platform Engineer (m/w/d)",
        ),
    )
    decoded = _model_output()
    decoded["letter_paragraphs"] = [
        "Die Aufgabe als Data Platform Engineer verbindet Datenplattformen und Engineering-Verantwortung auf eine für mich sehr passende Weise.",
        *decoded["letter_paragraphs"][1:],
    ]

    package = adapter._validate_output(
        decoded,
        context=context,
        as_of_date=date(2026, 9, 24),
    )

    assert package["status"] == "draft_for_review"


def test_grounded_company_team_salutation_is_allowed_without_named_contact() -> None:
    base = _context()
    context = replace(
        base,
        target=replace(
            base.target,
            company_name="Heartbeat AI GmbH",
            title="(Senior) Software Engineer - Device Connectivity (Go) (m/f/d)",
        ),
    )
    decoded = _model_output()
    decoded["salutation"] = "Liebes Heartbeat AI Team,"
    decoded["letter_paragraphs"] = [
        "Die Rolle im Bereich Device Connectivity bei Heartbeat AI verbindet Software Engineering mit technisch anspruchsvollen Schnittstellen.",
        *decoded["letter_paragraphs"][1:],
    ]

    package = adapter._validate_output(
        decoded,
        context=context,
        as_of_date=date(2026, 9, 24),
    )

    assert package["zone_replacements"]["base_application_letter"]["salutation"] == (
        "Liebes Heartbeat AI Team,"
    )
    assert package["automatic_semantic_repairs"] == []


def test_ungrounded_personal_salutation_is_repaired_without_provider_retry() -> None:
    base = _context()
    context = replace(
        base,
        target=replace(
            base.target,
            company_name="Heartbeat AI GmbH",
            title="(Senior) Software Engineer - Device Connectivity (Go) (m/f/d)",
        ),
    )
    decoded = _model_output()
    decoded["salutation"] = "Sehr geehrte Frau Schneider,"
    decoded["letter_paragraphs"] = [
        "Die Rolle im Bereich Device Connectivity bei Heartbeat AI verbindet Software Engineering mit technisch anspruchsvollen Schnittstellen.",
        *decoded["letter_paragraphs"][1:],
    ]

    package = adapter._validate_output(
        decoded,
        context=context,
        as_of_date=date(2026, 9, 24),
    )

    assert package["zone_replacements"]["base_application_letter"]["salutation"] == (
        "Guten Tag,"
    )
    assert package["automatic_semantic_repairs"] == [
        "ungrounded_salutation_replaced_with_generic"
    ]
