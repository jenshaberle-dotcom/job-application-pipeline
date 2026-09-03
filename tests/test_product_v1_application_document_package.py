from __future__ import annotations

from io import BytesIO
import json
from zipfile import ZipFile

from src.search_intelligence.product_v1_application_context import (
    ApprovedDocumentSnapshot,
    CandidateFactSnapshot,
    JobTargetSnapshot,
    ProductV1ApplicationContext,
)
from src.search_intelligence.product_v1_application_document_package import (
    build_application_document_package_payload,
    compose_application_document_texts,
)
from src.search_intelligence.product_v1_application_drafter import (
    ApplicationDraftFragment,
    ApplicationDraftPackage,
)


def _context() -> ProductV1ApplicationContext:
    return ProductV1ApplicationContext(
        target=JobTargetSnapshot(
            silver_job_id=434,
            product_rank=1,
            title="Data Engineer",
            company_name="Muster GmbH",
            source_name="personio:muster",
            source_url="https://muster.jobs.personio.de/job/1",
            product_readiness_status="rankable",
            authority_source="gold_product_v1_top_jobs",
        ),
        source_documents=(
            ApprovedDocumentSnapshot(
                document_type="base_cv",
                label="base cv",
                source_reference="local://base_cv.pdf",
                source_sha256="a" * 64,
                content=(
                    "Jens Haberle\n\n"
                    "Berufserfahrung\n"
                    "Data Engineering Projekt mit Python und PostgreSQL.\n\n"
                    "Weiterbildung\n"
                    "SQL und Datenmodellierung."
                ),
                source_hash_verified=True,
            ),
            ApprovedDocumentSnapshot(
                document_type="base_application_letter",
                label="base letter",
                source_reference="local://base_letter.pdf",
                source_sha256="b" * 64,
                content="Bestehendes Anschreiben als freigegebener Stilkontext.",
                source_hash_verified=True,
            ),
        ),
        approved_candidate_facts=(
            CandidateFactSnapshot(
                fact_key="candidate.python",
                category="experience",
                evidence_class="professional_employment",
                approval_status="approved",
                statement="Python Erfahrung",
                capability_tags=("python",),
                limitations=(),
                valid_from=None,
                valid_until=None,
            ),
        ),
        claim_plan=(),
        as_of_date=__import__("datetime").date(2026, 9, 3),
        candidate_profile_sha256="c" * 64,
        generation_ready=True,
    )


def _package() -> ApplicationDraftPackage:
    return ApplicationDraftPackage(
        status="draft_for_review",
        fragments=(
            ApplicationDraftFragment(
                kind="cv_summary",
                text="Stellenbezogenes Profil mit Python und SQL.",
                candidate_fact_keys=("candidate.python",),
                job_evidence=(),
            ),
            ApplicationDraftFragment(
                kind="cv_bullet",
                text="Python-basierte Datenverarbeitung für belastbare Pipelines.",
                candidate_fact_keys=("candidate.python",),
                job_evidence=("Python",),
            ),
            ApplicationDraftFragment(
                kind="letter_opening",
                text="Sehr geehrte Damen und Herren,\nDie Position verbindet Datenplattformen mit zuverlässiger Verarbeitung.",
                candidate_fact_keys=("candidate.python",),
                job_evidence=("Datenplattform",),
            ),
            ApplicationDraftFragment(
                kind="letter_fit",
                text="Meine freigegebene Python-Erfahrung passt zu den Aufgaben.",
                candidate_fact_keys=("candidate.python",),
                job_evidence=("Python",),
            ),
            ApplicationDraftFragment(
                kind="letter_closing",
                text="Ich freue mich auf ein persönliches Gespräch.\nMit freundlichen Grüßen\nJens Haberle",
                candidate_fact_keys=(),
                job_evidence=(),
            ),
        ),
    )


def _evidence_first_package() -> ApplicationDraftPackage:
    return ApplicationDraftPackage(
        status="draft_for_review",
        fragments=(
            ApplicationDraftFragment(
                kind="cv_summary",
                text="Freigegebene Kandidateninformation für den stellenbezogenen Profilkopf.",
                candidate_fact_keys=("candidate.python",),
                job_evidence=(),
            ),
            ApplicationDraftFragment(
                kind="letter_opening",
                text="Die Position ist für eine evidenzbasierte Bewerbung relevant.",
                candidate_fact_keys=("candidate.python",),
                job_evidence=("Datenplattform",),
            ),
            ApplicationDraftFragment(
                kind="letter_fit",
                text="Python ist als freigegebene Kandidatenkompetenz belegt.",
                candidate_fact_keys=("candidate.python",),
                job_evidence=("Python",),
            ),
            ApplicationDraftFragment(
                kind="letter_closing",
                text="Ich freue mich auf die Gelegenheit zum Austausch.",
                candidate_fact_keys=(),
                job_evidence=(),
            ),
        ),
    )


def test_complete_document_texts_preserve_base_cv_and_clean_letter_envelope() -> None:
    texts = compose_application_document_texts(context=_context(), package=_package())

    assert "STELLENBEZOGENES PROFIL" in texts.cv_text
    assert "RELEVANTE SCHWERPUNKTE" in texts.cv_text
    assert "BASISLEBENSLAUF" not in texts.cv_text
    assert "Berufserfahrung" in texts.cv_text
    assert "Data Engineering Projekt mit Python und PostgreSQL" in texts.cv_text
    assert texts.cv_text.count("Jens Haberle") == 1

    assert texts.letter_text.count("Sehr geehrte Damen und Herren") == 1
    assert texts.letter_text.count("Mit freundlichen Grüßen") == 1
    assert texts.letter_text.endswith("Jens Haberle")


def test_package_contains_four_review_files_and_zip() -> None:
    payload = build_application_document_package_payload(
        context=_context(),
        package=_package(),
    )

    assert payload["status"] == "ready_for_download"
    assert [item["key"] for item in payload["files"]] == [
        "cv_docx",
        "cv_pdf",
        "letter_docx",
        "letter_pdf",
        "application_zip",
    ]

    zip_item = next(item for item in payload["files"] if item["key"] == "application_zip")
    import base64

    with ZipFile(BytesIO(base64.b64decode(zip_item["content_base64"]))) as archive:
        names = archive.namelist()
        assert "manifest.json" in names
        assert len([name for name in names if name.endswith(".docx")]) == 2
        assert len([name for name in names if name.endswith(".pdf")]) == 2
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["status"] == "draft_for_review"
        assert manifest["boundaries"]["submission_action"] is False

    assert payload["boundaries"] == {
        "local_render": True,
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
        "draft_approval_authority": False,
        "application_authority": False,
    }


def test_evidence_first_minimal_review_package_still_exports_zip_bundle() -> None:
    payload = build_application_document_package_payload(
        context=_context(),
        package=_evidence_first_package(),
    )

    assert payload["status"] == "ready_for_download"
    assert [item["key"] for item in payload["files"]] == [
        "cv_docx",
        "cv_pdf",
        "letter_docx",
        "letter_pdf",
        "application_zip",
    ]
    assert "RELEVANTE SCHWERPUNKTE" not in payload["cv_text"]
    assert "BASISLEBENSLAUF" not in payload["cv_text"]
    assert "Berufserfahrung" in payload["cv_text"]
