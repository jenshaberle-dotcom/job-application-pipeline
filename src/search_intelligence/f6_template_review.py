"""F6 Slice-C local review/export service.

The service exposes only the two exact private F6 PDFs and their manifest-declared
text zones to the loopback Product UI.  It can render operator-edited text into
those zones by delegating to the already-qualified Slice-B renderer.

Private template bytes stay local.  No database, provider, application,
submission, or send authority is introduced here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pymupdf

from src.search_intelligence.f6_template_authority import (
    F6TemplateAuthorityStop,
    F6TemplateSpec,
    template_specs,
    validate_template_pdf,
)
from src.search_intelligence.f6_template_renderer import (
    F6TemplateRenderResult,
    F6TemplateRenderStop,
    render_template_pdf,
)


class F6TemplateReviewStop(ValueError):
    """Fail closed when local review/export cannot preserve F6 authority."""


@dataclass(frozen=True)
class F6ReviewDocument:
    spec: F6TemplateSpec
    template_pdf: bytes
    zones: tuple[dict[str, object], ...]

    def public_payload(self) -> dict[str, object]:
        return {
            "document_type": self.spec.document_type,
            "template_id": self.spec.template_id,
            "canonical_filename": self.spec.canonical_filename,
            "source_sha256": self.spec.sha256,
            "page_count": self.spec.page_count,
            "zones": [dict(zone) for zone in self.zones],
        }


@dataclass(frozen=True)
class F6RenderedReviewDocument:
    document_type: str
    canonical_filename: str
    pdf_bytes: bytes
    render_evidence: dict[str, object]


def _installed_template_path(*, root: Path, spec: F6TemplateSpec) -> Path:
    upload_root = root / "uploads"
    candidates = tuple(
        sorted(upload_root.glob(f"{spec.document_type}-{spec.sha256[:12]}-*.pdf"))
    )
    if len(candidates) != 1:
        raise F6TemplateReviewStop(
            "expected exactly one installed exact F6 template for "
            f"{spec.document_type}, found {len(candidates)}"
        )
    return candidates[0]


def _zone_rect(zone: Mapping[str, object]) -> pymupdf.Rect:
    raw = zone.get("bbox")
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise F6TemplateReviewStop(f"invalid F6 text-zone bbox: {zone.get('id')}")
    rect = pymupdf.Rect(*(float(value) for value in raw))
    if rect.is_empty or rect.is_infinite:
        raise F6TemplateReviewStop(
            f"invalid F6 text-zone rectangle: {zone.get('id')}"
        )
    return rect


def _zone_page_index(zone: Mapping[str, object], spec: F6TemplateSpec) -> int:
    try:
        page = int(zone["page"])
    except (KeyError, TypeError, ValueError) as exc:
        raise F6TemplateReviewStop(
            f"invalid F6 text-zone page: {zone.get('id')}"
        ) from exc
    if not 1 <= page <= spec.page_count:
        raise F6TemplateReviewStop(
            f"F6 text-zone page is outside template: {zone.get('id')}"
        )
    return page - 1


def load_review_document(*, root: Path, spec: F6TemplateSpec) -> F6ReviewDocument:
    path = _installed_template_path(root=root, spec=spec)
    template_pdf = path.read_bytes()
    try:
        validate_template_pdf(document_type=spec.document_type, content=template_pdf)
    except F6TemplateAuthorityStop as exc:
        raise F6TemplateReviewStop(str(exc)) from exc

    document = pymupdf.open(stream=template_pdf, filetype="pdf")
    try:
        zones: list[dict[str, object]] = []
        for zone in spec.editable_text_zones:
            zone_id = str(zone["id"])
            page_index = _zone_page_index(zone, spec)
            rect = _zone_rect(zone)
            source_text = document[page_index].get_textbox(rect).strip()
            zones.append(
                {
                    "id": zone_id,
                    "page": page_index + 1,
                    "bbox": [float(value) for value in zone["bbox"]],  # type: ignore[index]
                    "source_text": source_text,
                    "editable": True,
                }
            )
    finally:
        document.close()

    return F6ReviewDocument(
        spec=spec,
        template_pdf=template_pdf,
        zones=tuple(zones),
    )


def build_review_payload(*, root: Path) -> dict[str, object]:
    private_root = root.expanduser().resolve()
    documents = tuple(
        load_review_document(root=private_root, spec=spec)
        for spec in template_specs()
    )
    return {
        "schema": "job_application_pipeline.f6_template_review.v1",
        "status": "ready",
        "campaign": "F6",
        "slice": "C",
        "templates": [document.public_payload() for document in documents],
        "layout_policy": "pixel_bound_text_zones_only",
        "private_template_bytes_exposed": False,
        "human_review_required": True,
        "draft_approval_authority": False,
        "application_authority": False,
        "submission_authority": False,
        "send_authority": False,
    }


def _normalize_document_replacements(
    *,
    spec: F6TemplateSpec,
    raw: object,
) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise F6TemplateReviewStop(
            f"replacements for {spec.document_type} must be an object"
        )
    declared = {str(zone["id"]) for zone in spec.editable_text_zones}
    unknown = sorted(str(key) for key in raw if str(key) not in declared)
    if unknown:
        raise F6TemplateReviewStop(
            "replacement targets undeclared F6 text zone(s): " + ", ".join(unknown)
        )
    result: dict[str, str] = {}
    for key, value in raw.items():
        zone_id = str(key)
        if not isinstance(value, str):
            raise F6TemplateReviewStop(f"replacement for {zone_id} must be text")
        result[zone_id] = value
    return result


def render_review_package(
    *,
    root: Path,
    replacements_by_document: object,
) -> tuple[F6RenderedReviewDocument, ...]:
    if not isinstance(replacements_by_document, Mapping):
        raise F6TemplateReviewStop("documents must be an object")

    specs = {spec.document_type: spec for spec in template_specs()}
    if set(str(key) for key in replacements_by_document) != set(specs):
        raise F6TemplateReviewStop(
            "final F6 review export requires exactly base_cv and "
            "base_application_letter"
        )

    private_root = root.expanduser().resolve()
    rendered: list[F6RenderedReviewDocument] = []
    for document_type in ("base_cv", "base_application_letter"):
        spec = specs[document_type]
        review = load_review_document(root=private_root, spec=spec)
        replacements = _normalize_document_replacements(
            spec=spec,
            raw=replacements_by_document[document_type],
        )

        if replacements:
            try:
                result: F6TemplateRenderResult = render_template_pdf(
                    document_type=document_type,
                    template_pdf=review.template_pdf,
                    replacements=replacements,
                )
            except (F6TemplateAuthorityStop, F6TemplateRenderStop) as exc:
                raise F6TemplateReviewStop(str(exc)) from exc
            pdf_bytes = result.pdf_bytes
            evidence = result.public_payload()
        else:
            pdf_bytes = review.template_pdf
            evidence = {
                "schema": "job_application_pipeline.f6_template_render.v1",
                "status": "source_template_for_review",
                "document_type": document_type,
                "template_id": spec.template_id,
                "source_sha256": spec.sha256,
                "output_sha256": spec.sha256,
                "applied_zone_ids": [],
                "page_diff_evidence": [],
                "outside_zone_pixel_identity": True,
                "layout_policy": "pixel_bound_text_zones_only",
                "human_review_required": True,
                "draft_approval_authority": False,
                "application_authority": False,
                "submission_authority": False,
                "send_authority": False,
            }

        rendered.append(
            F6RenderedReviewDocument(
                document_type=document_type,
                canonical_filename=spec.canonical_filename,
                pdf_bytes=pdf_bytes,
                render_evidence=evidence,
            )
        )

    return tuple(rendered)


__all__ = [
    "F6RenderedReviewDocument",
    "F6ReviewDocument",
    "F6TemplateReviewStop",
    "build_review_payload",
    "load_review_document",
    "render_review_package",
]
