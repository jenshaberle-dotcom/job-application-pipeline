"""Compose a review-only application package from grounded draft fragments.

The provider never creates file bytes. This module combines the validated draft with
approved local base-document text and renders DOCX/PDF variants locally. A ZIP is
assembled locally as a convenience wrapper around the same four review files. It
performs no database write, approval, submission or send action.
"""
from __future__ import annotations

from base64 import b64encode
from io import BytesIO
import json
from zipfile import ZIP_DEFLATED, ZipFile

from src.search_intelligence.product_v1_application_context import (
    ProductV1ApplicationContext,
)
from src.search_intelligence.product_v1_application_document_export import (
    ApplicationDocumentTextBundle,
    RenderedApplicationFile,
    render_application_document_bundle,
)
from src.search_intelligence.product_v1_application_drafter import (
    ApplicationDraftPackage,
)


class ApplicationDocumentPackageStop(ValueError):
    """Fail closed when a validated draft cannot form complete documents."""


def _base_document(context: ProductV1ApplicationContext, document_type: str) -> str:
    matches = [
        document.content.strip()
        for document in context.source_documents
        if document.document_type == document_type and document.content.strip()
    ]
    if len(matches) != 1:
        raise ApplicationDocumentPackageStop(
            f"exactly one approved {document_type} text is required"
        )
    return matches[0]


def _candidate_name(base_cv: str) -> str:
    for raw in base_cv.splitlines():
        line = " ".join(raw.split())
        if not line or len(line) > 80 or "@" in line or "http" in line.casefold():
            continue
        words = line.split()
        if 2 <= len(words) <= 5 and all(any(char.isalpha() for char in word) for word in words):
            return line
    return "Candidate"


def _fragment_texts(package: ApplicationDraftPackage, kind: str) -> tuple[str, ...]:
    return tuple(fragment.text.strip() for fragment in package.fragments if fragment.kind == kind)


def compose_application_document_texts(
    *,
    context: ProductV1ApplicationContext,
    package: ApplicationDraftPackage,
) -> ApplicationDocumentTextBundle:
    """Build complete review documents while preserving the approved base CV verbatim."""

    if package.status != "draft_for_review":
        raise ApplicationDocumentPackageStop("validated draft_for_review package is required")

    base_cv = _base_document(context, "base_cv")
    _base_document(context, "base_application_letter")

    summaries = _fragment_texts(package, "cv_summary")
    bullets = _fragment_texts(package, "cv_bullet")
    opening = _fragment_texts(package, "letter_opening")
    fit = _fragment_texts(package, "letter_fit")
    closing = _fragment_texts(package, "letter_closing")

    if len(summaries) != 1 or len(bullets) > 6:
        raise ApplicationDocumentPackageStop(
            "complete CV adaptation requires one summary and at most six grounded bullets"
        )
    if len(opening) != 1 or not 1 <= len(fit) <= 4 or len(closing) != 1:
        raise ApplicationDocumentPackageStop(
            "complete letter requires opening, grounded fit content and closing"
        )

    cv_focus = [
        "STELLENBEZOGENES PROFIL",
        summaries[0],
    ]
    if bullets:
        cv_focus.extend(
            [
                "RELEVANTE SCHWERPUNKTE",
                *[f"• {text}" for text in bullets],
            ]
        )
    cv_focus.extend(["BASISLEBENSLAUF", base_cv])
    cv_text = "\n\n".join(cv_focus)

    candidate_name = _candidate_name(base_cv)
    application_date = context.as_of_date.strftime("%d.%m.%Y")
    letter_parts = [
        candidate_name,
        context.target.company_name,
        application_date,
        f"Bewerbung als {context.target.title}",
        "Sehr geehrte Damen und Herren,",
        opening[0],
        *fit,
        closing[0],
        "Mit freundlichen Grüßen",
        candidate_name,
    ]
    letter_text = "\n\n".join(letter_parts)

    return ApplicationDocumentTextBundle(
        silver_job_id=context.target.silver_job_id,
        company_name=context.target.company_name,
        cv_text=cv_text,
        letter_text=letter_text,
    )


def _zip_bundle(files: tuple[RenderedApplicationFile, ...]) -> RenderedApplicationFile:
    """Wrap the four canonical review files plus a checksum manifest in one ZIP."""

    if len(files) != 4:
        raise ApplicationDocumentPackageStop("ZIP wrapper requires exactly four review files")
    manifest = {
        "schema": "job_application_pipeline.application_download_bundle.v1",
        "status": "draft_for_review",
        "files": [file.manifest_entry() for file in files],
        "boundaries": {
            "review_required": True,
            "submission_action": False,
            "send_action": False,
        },
    }
    output = BytesIO()
    with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
        for file in files:
            archive.writestr(file.filename, file.content)
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
    content = output.getvalue()
    if not content.startswith(b"PK"):
        raise ApplicationDocumentPackageStop("ZIP renderer produced invalid output")
    first = files[0].filename.rsplit("-cv.docx", 1)[0]
    return RenderedApplicationFile(
        key="application_zip",
        filename=f"{first}-review-package.zip",
        media_type="application/zip",
        content=content,
    )


def build_application_document_package_payload(
    *,
    context: ProductV1ApplicationContext,
    package: ApplicationDraftPackage,
) -> dict[str, object]:
    """Return browser-downloadable local files plus human-readable complete previews."""

    texts = compose_application_document_texts(context=context, package=package)
    review_files = render_application_document_bundle(texts)
    files = (*review_files, _zip_bundle(review_files))
    return {
        "status": "ready_for_download",
        "cv_text": texts.cv_text,
        "letter_text": texts.letter_text,
        "files": [
            item.manifest_entry()
            | {"content_base64": b64encode(item.content).decode("ascii")}
            for item in files
        ],
        "boundaries": {
            "local_render": True,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
            "draft_approval_authority": False,
            "application_authority": False,
        },
    }


__all__ = [
    "ApplicationDocumentPackageStop",
    "build_application_document_package_payload",
    "compose_application_document_texts",
]
