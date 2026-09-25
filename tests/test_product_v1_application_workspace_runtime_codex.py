from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from scripts import product_v1_application_workspace_runtime_quality as runtime
from src.search_intelligence.f6_template_authority import template_spec
from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    build_product_v1_application_context,
)


DETAIL = "AI Automation Engineer. accompio sucht Python und PostgreSQL für AI Automation."


def _document(kind: str) -> ApplicationSourceDocumentSnapshot:
    return ApplicationSourceDocumentSnapshot(
        document_type=kind,
        source_label=kind,
        source_reference=f"local://{kind}.pdf",
        content_sha256=template_spec(kind).sha256,
        content=(
            "Jens Haberle. Python PostgreSQL System Engineering."
            if kind == "base_cv"
            else "OLD EMPLOYER LETTER MUST NEVER BECOME FALLBACK CONTENT."
        ),
        status="approved",
        source_hash_verified=True,
    )


def _context():
    return build_product_v1_application_context(
        target=ApplicationTargetSnapshot(
            silver_job_id=626,
            product_rank=None,
            title="AI Automation Engineer",
            company_name="accompio",
            source_url="https://jobs.example/626",
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
                statement="Python und PostgreSQL werden in eigenen Projekten eingesetzt.",
                capability_tags=("Python", "PostgreSQL"),
                limitations=(),
            ),
        ),
        source_documents=(_document("base_cv"), _document("base_application_letter")),
        as_of_date=date(2026, 9, 24),
    )


def _load(_silver_job_id: int):
    return (
        _context(),
        "https://jobs.example/626",
        "AI Automation Engineer",
        "exact_persisted_observation",
        0,
    )


def test_capacity_unavailable_never_falls_back_to_deterministic_prose(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "load_application_workspace", _load)
    monkeypatch.setattr(runtime, "require_live_application_target", lambda _job_id: None)
    monkeypatch.setattr(
        runtime,
        "request_codex_application_adaptation",
        lambda **_kwargs: SimpleNamespace(
            package=None,
            attempted=True,
            model="gpt-5.6-sol",
            codex_version="codex-cli test",
            reason_code="codex_capacity_unavailable",
            reason="Codex usage capacity is unavailable.",
        ),
    )

    payload = runtime.generate_application_draft_payload(626)

    assert payload["status"] == "draft_unavailable"
    assert payload["reason_code"] == "codex_capacity_unavailable"
    assert payload["fallback_generated"] is False
    assert payload["fallback_policy"] == "no_low_quality_prose_fallback"
    assert payload["codex_requests"] == 1
    assert payload.get("package") is None
    assert payload["database_writes"] == 0
    assert payload["submission_writes"] == 0
    assert payload["send_actions"] == 0


def test_codex_package_passes_direct_zone_replacements_to_review_ui(monkeypatch) -> None:
    monkeypatch.setattr(runtime, "load_application_workspace", _load)
    monkeypatch.setattr(runtime, "require_live_application_target", lambda _job_id: None)
    monkeypatch.setattr(runtime, "_probe_generated_package_overflows", lambda _package: ())
    monkeypatch.setattr(
        runtime,
        "request_codex_application_adaptation",
        lambda **_kwargs: SimpleNamespace(
            package={
                "status": "draft_for_review",
                "rationale": "targeted",
                "preview": {
                    "cv_short_profile": "Targeted CV profile",
                    "cv_competency_profile": "Python · PostgreSQL",
                    "application_letter": "Sehr geehrte Damen und Herren,\n\nTargeted letter",
                },
                "zone_replacements": {
                    "base_cv": {"p1.short_profile": "Targeted CV profile"},
                    "base_application_letter": {
                        "recipient.block": "accompio",
                        "subject": "Bewerbung als AI Automation Engineer",
                        "salutation": "Sehr geehrte Damen und Herren,",
                    },
                },
                "draft_approval_authority": False,
                "application_authority": False,
                "submission_authority": False,
                "send_authority": False,
            },
            attempted=True,
            model="gpt-5.6-sol",
            codex_version="codex-cli test",
            reason_code=None,
            reason=None,
        ),
    )

    payload = runtime.generate_application_draft_payload(626)

    assert payload["status"] == "draft_for_review"
    assert payload["draft_mode"] == "codex_embedded_v1"
    assert payload["fallback_generated"] is False
    assert payload["base_cv_text_shared_with_codex"] is True
    assert payload["base_application_letter_text_shared_with_codex"] is True
    assert payload["vacancy_text_shared_with_codex"] is True
    assert payload["package"]["zone_replacements"]["base_application_letter"]["recipient.block"] == "accompio"
    assert payload["package"]["source_manifest_sha256"]
    assert payload["provider_requests"] == 1
    assert payload["database_writes"] == 0



def test_salutation_overflow_is_repaired_deterministically_without_extra_codex(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime, "load_application_workspace", _load)
    monkeypatch.setattr(runtime, "require_live_application_target", lambda _job_id: None)

    package = {
        "status": "draft_for_review",
        "language": "de",
        "contact_name": "Paulina Krzeminski",
        "preview": {
            "cv_short_profile": "Targeted CV profile",
            "cv_competency_profile": "Python · PostgreSQL",
            "application_letter": "Sehr geehrte Frau Krzeminski,\n\nTargeted letter",
        },
        "zone_replacements": {
            "base_cv": {"p1.short_profile": "Targeted CV profile"},
            "base_application_letter": {
                "recipient.block": "accompio\nPaulina Krzeminski",
                "salutation": "Sehr geehrte Frau Krzeminski,",
                "body.paragraph_1": "Targeted letter",
                "closing.formula": "Mit freundlichen Grüßen",
            },
        },
    }
    calls = []

    def fake_codex(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            package=package,
            attempted=True,
            model="gpt-5.6-sol",
            codex_version="codex-cli test",
            reason_code=None,
            reason=None,
        )

    probes = iter(
        [
            ("base_application_letter:salutation",),
            (),
        ]
    )
    monkeypatch.setattr(runtime, "request_codex_application_adaptation", fake_codex)
    monkeypatch.setattr(
        runtime,
        "_probe_generated_package_overflows",
        lambda _package: next(probes),
    )

    payload = runtime.generate_application_draft_payload(626)

    assert payload["status"] == "draft_for_review"
    assert payload["layout_fit_status"] == "exact_template_preflight_pass"
    assert payload["layout_repair_attempts"] == 0
    assert payload["codex_requests"] == 1
    assert len(calls) == 1
    assert payload["automatic_layout_repairs"] == [
        "base_application_letter:salutation=neutral_compact"
    ]
    assert (
        payload["package"]["zone_replacements"]["base_application_letter"][
            "salutation"
        ]
        == "Guten Tag,"
    )
    assert payload["package"]["preview"]["application_letter"].startswith("Guten Tag,")


def test_semantic_overflow_triggers_bounded_automatic_codex_repair(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime, "load_application_workspace", _load)
    monkeypatch.setattr(runtime, "require_live_application_target", lambda _job_id: None)

    first_package = {
        "status": "draft_for_review",
        "language": "de",
        "contact_name": "",
        "preview": {
            "cv_short_profile": "Targeted CV profile",
            "cv_competency_profile": "Python · PostgreSQL",
            "application_letter": "Guten Tag,\n\n" + ("Langer Absatz " * 20),
        },
        "zone_replacements": {
            "base_cv": {"p1.short_profile": "Targeted CV profile"},
            "base_application_letter": {
                "salutation": "Guten Tag,",
                "body.paragraph_1": "Langer Absatz " * 20,
            },
        },
    }
    repaired_package = {
        **first_package,
        "preview": {
            **first_package["preview"],
            "application_letter": "Guten Tag,\n\nKurzer, gezielter Absatz.",
        },
        "zone_replacements": {
            "base_cv": {"p1.short_profile": "Targeted CV profile"},
            "base_application_letter": {
                "salutation": "Guten Tag,",
                "body.paragraph_1": "Kurzer, gezielter Absatz.",
            },
        },
    }
    calls = []

    def fake_codex(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            package=first_package if len(calls) == 1 else repaired_package,
            attempted=True,
            model="gpt-5.6-sol",
            codex_version="codex-cli test",
            reason_code=None,
            reason=None,
        )

    probes = iter(
        [
            ("base_application_letter:body.paragraph_1",),
            (),
        ]
    )
    monkeypatch.setattr(runtime, "request_codex_application_adaptation", fake_codex)
    monkeypatch.setattr(
        runtime,
        "_probe_generated_package_overflows",
        lambda _package: next(probes),
    )

    payload = runtime.generate_application_draft_payload(626)

    assert payload["status"] == "draft_for_review"
    assert payload["layout_fit_status"] == "exact_template_preflight_pass"
    assert payload["layout_repair_attempts"] == 1
    assert payload["codex_requests"] == 2
    assert len(calls) == 2
    assert calls[1]["layout_feedback"] == (
        "base_application_letter:body.paragraph_1",
    )
    assert calls[1]["previous_package"] == first_package


def test_unresolved_layout_overflow_never_falls_back_to_manual_or_filler(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime, "load_application_workspace", _load)
    monkeypatch.setattr(runtime, "require_live_application_target", lambda _job_id: None)

    package = {
        "status": "draft_for_review",
        "language": "de",
        "contact_name": "",
        "preview": {
            "cv_short_profile": "Targeted CV profile",
            "cv_competency_profile": "Python · PostgreSQL",
            "application_letter": "Guten Tag,\n\n" + ("Langer Absatz " * 20),
        },
        "zone_replacements": {
            "base_cv": {"p1.short_profile": "Targeted CV profile"},
            "base_application_letter": {
                "salutation": "Guten Tag,",
                "body.paragraph_1": "Langer Absatz " * 20,
            },
        },
    }

    monkeypatch.setattr(
        runtime,
        "request_codex_application_adaptation",
        lambda **_kwargs: SimpleNamespace(
            package=package,
            attempted=True,
            model="gpt-5.6-sol",
            codex_version="codex-cli test",
            reason_code=None,
            reason=None,
        ),
    )
    monkeypatch.setattr(
        runtime,
        "_probe_generated_package_overflows",
        lambda _package: ("base_application_letter:body.paragraph_1",),
    )

    payload = runtime.generate_application_draft_payload(626)

    assert payload["status"] == "draft_unavailable"
    assert payload["reason_code"] == "f6_template_fit_unresolved"
    assert payload["codex_requests"] == 3
    assert payload["layout_overflows"] == [
        "base_application_letter:body.paragraph_1"
    ]
    assert payload["fallback_generated"] is False
    assert payload.get("package") is None
