from base64 import b64decode
from datetime import date
from types import SimpleNamespace

from pypdf import PdfReader
from io import BytesIO

from src.search_intelligence.product_v1_application_document_package import (
    build_application_document_package_payload,
    compose_application_document_texts,
)


def _context():
    return SimpleNamespace(
        target=SimpleNamespace(
            silver_job_id=434,
            company_name="Muster Data GmbH",
            title="(Junior) Data Engineer - Data Platform (m/f/d)",
        ),
        as_of_date=date(2026, 9, 3),
        source_documents=(
            SimpleNamespace(
                document_type="base_cv",
                content=(
                    "Jens Haberle\n\n"
                    "Berufserfahrung\n"
                    "Data Engineering Projekt mit Python und PostgreSQL.\n\n"
                    "Weiterbildung\nSQL und Datenmodellierung."
                ),
            ),
            SimpleNamespace(
                document_type="base_application_letter",
                content=(
                    "Jens Haberle\n\nSehr geehrte Damen und Herren,\n\n"
                    "bisheriger Bewerbungstext.\n\nMit freundlichen Grüßen\nJens Haberle"
                ),
            ),
        ),
    )


def _package():
    def fragment(kind: str, text: str):
        return SimpleNamespace(kind=kind, text=text)

    return SimpleNamespace(
        status="draft_for_review",
        fragments=(
            fragment(
                "cv_summary",
                "Data Engineer mit Fokus auf strukturierte Datenverarbeitung, Python und SQL.",
            ),
            fragment("cv_bullet", "Entwicklung reproduzierbarer Datenpipelines."),
            fragment("cv_bullet", "Praktische Arbeit mit Python, SQL und PostgreSQL."),
            fragment("cv_bullet", "Fokus auf Datenqualität und nachvollziehbare Verarbeitung."),
            fragment(
                "letter_opening",
                "Die Rolle verbindet Datenplattformarbeit mit zuverlässiger Datenverarbeitung.",
            ),
            fragment(
                "letter_fit",
                "Meine praktische Arbeit an Datenpipelines knüpft direkt an diese Aufgaben an.",
            ),
            fragment(
                "letter_fit",
                "Python, SQL und Datenqualität bilden dabei den fachlichen Schwerpunkt.",
            ),
            fragment(
                "letter_closing",
                "Gern erläutere ich Ihnen meinen möglichen Beitrag in einem persönlichen Gespräch.",
            ),
        ),
    )


def test_complete_texts_keep_base_cv_and_form_coherent_letter() -> None:
    bundle = compose_application_document_texts(context=_context(), package=_package())

    assert "STELLENBEZOGENES PROFIL" in bundle.cv_text
    assert "Data Engineering Projekt mit Python und PostgreSQL" in bundle.cv_text
    assert "RELEVANTE SCHWERPUNKTE" in bundle.cv_text
    assert "Muster Data GmbH" in bundle.letter_text
    assert "Bewerbung als (Junior) Data Engineer" in bundle.letter_text
    assert "Sehr geehrte Damen und Herren" in bundle.letter_text
    assert "Mit freundlichen Grüßen" in bundle.letter_text
    assert "bisheriger Bewerbungstext" not in bundle.letter_text


def test_package_exposes_four_downloadable_local_files() -> None:
    payload = build_application_document_package_payload(
        context=_context(),
        package=_package(),
    )

    assert payload["status"] == "ready_for_download"
    files = payload["files"]
    assert isinstance(files, list)
    assert [item["key"] for item in files] == [
        "cv_docx",
        "cv_pdf",
        "letter_docx",
        "letter_pdf",
    ]

    for item in files:
        content = b64decode(item["content_base64"])
        assert len(content) == item["byte_count"]
        assert len(item["content_sha256"]) == 64

    cv_pdf = next(item for item in files if item["key"] == "cv_pdf")
    cv_pdf_text = "\n".join(
        page.extract_text() or ""
        for page in PdfReader(BytesIO(b64decode(cv_pdf["content_base64"]))).pages
    )
    assert "STELLENBEZOGENES PROFIL" in cv_pdf_text

    assert payload["boundaries"] == {
        "local_render": True,
        "database_writes": 0,
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
        "draft_approval_authority": False,
        "application_authority": False,
    }
