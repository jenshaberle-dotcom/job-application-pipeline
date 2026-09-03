"""Local four-file export for a complete Product V1 application draft.

The renderer is deliberately provider- and database-free. Callers must supply the
already-reviewed complete CV and application-letter text. It creates editable DOCX
and portable PDF variants locally and returns bytes plus integrity metadata. It does
not persist, submit, send or grant application/product authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape
from io import BytesIO
import re

from docx import Document
from docx.enum.section import WD_SECTION
from docx.shared import Cm, Pt
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


_MAX_DOCUMENT_CHARS = 80_000
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class ApplicationDocumentExportStop(ValueError):
    """Fail closed when a complete local export bundle is not renderable."""


@dataclass(frozen=True)
class ApplicationDocumentTextBundle:
    silver_job_id: int
    company_name: str
    cv_text: str
    letter_text: str


@dataclass(frozen=True)
class RenderedApplicationFile:
    key: str
    filename: str
    media_type: str
    content: bytes

    @property
    def content_sha256(self) -> str:
        return sha256(self.content).hexdigest()

    def manifest_entry(self) -> dict[str, object]:
        return {
            "key": self.key,
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_count": len(self.content),
            "content_sha256": self.content_sha256,
        }


def _required_text(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ApplicationDocumentExportStop(f"{field} is required")
    if len(text) > _MAX_DOCUMENT_CHARS:
        raise ApplicationDocumentExportStop(f"{field} exceeds local export bound")
    return text


def _company_slug(company_name: str) -> str:
    normalized = company_name.casefold().replace("ß", "ss")
    normalized = (
        normalized.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    )
    slug = _SLUG_RE.sub("-", normalized).strip("-")
    return slug[:48] or "employer"


def _paragraphs(text: str) -> tuple[str, ...]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    blocks = tuple(
        " ".join(part.split())
        for part in re.split(r"\n\s*\n", normalized)
        if part.strip()
    )
    return blocks or (" ".join(normalized.split()),)


def _render_docx(text: str) -> bytes:
    document = Document()
    section = document.sections[0]
    section.start_type = WD_SECTION.NEW_PAGE
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)

    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.08

    for block in _paragraphs(text):
        document.add_paragraph(block)

    output = BytesIO()
    document.save(output)
    content = output.getvalue()
    if not content.startswith(b"PK"):
        raise ApplicationDocumentExportStop("DOCX renderer produced invalid output")
    return content


def _render_pdf(text: str) -> bytes:
    output = BytesIO()
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "ApplicationBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        alignment=TA_LEFT,
        spaceAfter=7,
    )
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Application draft for review",
        author="Deep Ocean Intelligence",
    )
    story = []
    for block in _paragraphs(text):
        story.append(Paragraph(escape(block), body))
        story.append(Spacer(1, 2 * mm))
    document.build(story)
    content = output.getvalue()
    if not content.startswith(b"%PDF"):
        raise ApplicationDocumentExportStop("PDF renderer produced invalid output")
    return content


def render_application_document_bundle(
    bundle: ApplicationDocumentTextBundle,
) -> tuple[RenderedApplicationFile, ...]:
    if bundle.silver_job_id <= 0:
        raise ApplicationDocumentExportStop("silver_job_id must be positive")
    company = _required_text(bundle.company_name, field="company_name")
    cv_text = _required_text(bundle.cv_text, field="cv_text")
    letter_text = _required_text(bundle.letter_text, field="letter_text")
    prefix = f"application-{bundle.silver_job_id}-{_company_slug(company)}"

    cv_docx = _render_docx(cv_text)
    cv_pdf = _render_pdf(cv_text)
    letter_docx = _render_docx(letter_text)
    letter_pdf = _render_pdf(letter_text)

    return (
        RenderedApplicationFile(
            key="cv_docx",
            filename=f"{prefix}-cv.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=cv_docx,
        ),
        RenderedApplicationFile(
            key="cv_pdf",
            filename=f"{prefix}-cv.pdf",
            media_type="application/pdf",
            content=cv_pdf,
        ),
        RenderedApplicationFile(
            key="letter_docx",
            filename=f"{prefix}-letter.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content=letter_docx,
        ),
        RenderedApplicationFile(
            key="letter_pdf",
            filename=f"{prefix}-letter.pdf",
            media_type="application/pdf",
            content=letter_pdf,
        ),
    )


__all__ = [
    "ApplicationDocumentExportStop",
    "ApplicationDocumentTextBundle",
    "RenderedApplicationFile",
    "render_application_document_bundle",
]
