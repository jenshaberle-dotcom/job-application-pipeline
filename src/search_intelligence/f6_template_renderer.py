"""F6 template-bound PDF rendering with pixel-bound outside-zone proof.

This module is the rendering authority for F6 Slice B only. It accepts only one
of the two exact private PDFs already admitted by `f6_template_authority`,
changes text only inside manifest-declared zones, fails closed on overflow, and
proves that rendered pixels outside all declared zones are unchanged.

It grants no draft approval, application, submission, send, or product authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape
import math
from typing import Mapping

import pymupdf

from src.search_intelligence.f6_template_authority import (
    F6TemplateSpec,
    validate_template_pdf,
)


_RENDER_ZOOM = 1.5
_ZONE_MASK_PAD_PIXELS = 2
_MAX_REPLACEMENT_CHARS = 4_000


class F6TemplateRenderStop(ValueError):
    """Fail closed when a template-bound render cannot preserve F6 authority."""


@dataclass(frozen=True)
class F6PageDiffEvidence:
    page: int
    width_px: int
    height_px: int
    compared_pixels: int
    changed_pixels: int
    outside_zone_sha256_before: str
    outside_zone_sha256_after: str

    def public_payload(self) -> dict[str, object]:
        return {
            "page": self.page,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "compared_pixels": self.compared_pixels,
            "changed_pixels": self.changed_pixels,
            "outside_zone_sha256_before": self.outside_zone_sha256_before,
            "outside_zone_sha256_after": self.outside_zone_sha256_after,
            "outside_zone_pixel_identity": self.changed_pixels == 0,
        }


@dataclass(frozen=True)
class F6TemplateRenderResult:
    document_type: str
    template_id: str
    source_sha256: str
    output_sha256: str
    applied_zone_ids: tuple[str, ...]
    page_diff_evidence: tuple[F6PageDiffEvidence, ...]
    pdf_bytes: bytes

    @property
    def outside_zone_pixel_identity(self) -> bool:
        return all(item.changed_pixels == 0 for item in self.page_diff_evidence)

    def public_payload(self) -> dict[str, object]:
        return {
            "schema": "job_application_pipeline.f6_template_render.v1",
            "status": "rendered_for_review",
            "document_type": self.document_type,
            "template_id": self.template_id,
            "source_sha256": self.source_sha256,
            "output_sha256": self.output_sha256,
            "applied_zone_ids": list(self.applied_zone_ids),
            "page_diff_evidence": [
                item.public_payload() for item in self.page_diff_evidence
            ],
            "outside_zone_pixel_identity": self.outside_zone_pixel_identity,
            "layout_policy": "pixel_bound_text_zones_only",
            "human_review_required": True,
            "draft_approval_authority": False,
            "application_authority": False,
            "submission_authority": False,
            "send_authority": False,
        }


def _zone_map(spec: F6TemplateSpec) -> dict[str, Mapping[str, object]]:
    zones: dict[str, Mapping[str, object]] = {}
    for zone in spec.editable_text_zones:
        zone_id = str(zone["id"])
        if zone_id in zones:
            raise F6TemplateRenderStop(f"duplicate F6 text-zone id: {zone_id}")
        zones[zone_id] = zone
    return zones


def _zone_rect(zone: Mapping[str, object]) -> pymupdf.Rect:
    raw = zone.get("bbox")
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        raise F6TemplateRenderStop(f"invalid F6 text-zone bbox: {zone.get('id')}")
    rect = pymupdf.Rect(*(float(value) for value in raw))
    if rect.is_empty or rect.is_infinite:
        raise F6TemplateRenderStop(f"invalid F6 text-zone rectangle: {zone.get('id')}")
    return rect


def _page_index(zone: Mapping[str, object], spec: F6TemplateSpec) -> int:
    try:
        page = int(zone["page"])
    except (KeyError, TypeError, ValueError) as exc:
        raise F6TemplateRenderStop(
            f"invalid F6 text-zone page: {zone.get('id')}"
        ) from exc
    if not 1 <= page <= spec.page_count:
        raise F6TemplateRenderStop(f"F6 text-zone page is outside template: {zone.get('id')}")
    return page - 1


def _normalize_replacements(
    *, spec: F6TemplateSpec, replacements: Mapping[str, object]
) -> dict[str, str]:
    zones = _zone_map(spec)
    unknown = sorted(set(replacements) - set(zones))
    if unknown:
        raise F6TemplateRenderStop(
            "replacement targets undeclared F6 text zone(s): " + ", ".join(unknown)
        )
    result: dict[str, str] = {}
    for zone_id, raw in replacements.items():
        if raw is None:
            text = ""
        elif isinstance(raw, str):
            text = raw
        else:
            raise F6TemplateRenderStop(f"replacement for {zone_id} must be text")
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(text) > _MAX_REPLACEMENT_CHARS:
            raise F6TemplateRenderStop(
                f"replacement for {zone_id} exceeds {_MAX_REPLACEMENT_CHARS} characters"
            )
        result[zone_id] = text
    if not result:
        raise F6TemplateRenderStop("at least one F6 text-zone replacement is required")
    return result


def _source_text_style(
    page: pymupdf.Page, rect: pymupdf.Rect
) -> tuple[float, str, bool]:
    sizes: list[float] = []
    colors: list[int] = []
    bold_votes = 0
    span_count = 0
    payload = page.get_text("dict", clip=rect)
    for block in payload.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = float(span.get("size") or 0)
                if size > 0:
                    sizes.append(size)
                colors.append(int(span.get("color") or 0))
                flags = int(span.get("flags") or 0)
                bold_votes += int(bool(flags & 16))
                span_count += 1
    size = sorted(sizes)[len(sizes) // 2] if sizes else 9.5
    size = max(6.0, min(14.0, size))
    color = colors[0] if colors else 0
    color_hex = f"#{color & 0xFFFFFF:06x}"
    return size, color_hex, bool(span_count and bold_votes * 2 >= span_count)


def _zone_html(
    *, page: pymupdf.Page, rect: pymupdf.Rect, zone_id: str, text: str
) -> tuple[str, str]:
    font_size, color, bold = _source_text_style(page, rect)
    align = "right" if zone_id == "date" or zone_id.endswith(".date") else "left"
    weight = "700" if bold else "400"
    css = (
        "html,body,p{margin:0;padding:0;}"
        "p{font-family:sans-serif;"
        f"font-size:{font_size:.2f}pt;line-height:1.10;"
        f"color:{color};font-weight:{weight};text-align:{align};"
        "}"
    )
    body = "<br>".join(escape(line) for line in text.split("\n"))
    return f"<p>{body}</p>", css


def _text_fits(
    *, page: pymupdf.Page, rect: pymupdf.Rect, zone_id: str, text: str
) -> bool:
    if not text:
        return True
    html, css = _zone_html(page=page, rect=rect, zone_id=zone_id, text=text)
    scratch = pymupdf.open()
    try:
        probe = scratch.new_page(width=page.rect.width, height=page.rect.height)
        spare_height, scale = probe.insert_htmlbox(
            rect,
            html,
            css=css,
            scale_low=1,
            overlay=True,
        )
    finally:
        scratch.close()
    return spare_height >= 0 and math.isclose(
        float(scale), 1.0, rel_tol=0, abs_tol=1e-9
    )


def _assert_text_fits(
    *, page: pymupdf.Page, rect: pymupdf.Rect, zone_id: str, text: str
) -> None:
    if not _text_fits(page=page, rect=rect, zone_id=zone_id, text=text):
        raise F6TemplateRenderStop(
            f"replacement text does not fit frozen F6 zone without scaling: {zone_id}"
        )


def _apply_text_zone(
    *, page: pymupdf.Page, rect: pymupdf.Rect, zone_id: str, text: str
) -> None:
    page.add_redact_annot(rect, fill=False)
    page.apply_redactions(images=0, graphics=0, text=0)
    if not text:
        return
    html, css = _zone_html(page=page, rect=rect, zone_id=zone_id, text=text)
    spare_height, scale = page.insert_htmlbox(
        rect,
        html,
        css=css,
        scale_low=1,
        overlay=True,
    )
    if spare_height < 0 or not math.isclose(float(scale), 1.0, rel_tol=0, abs_tol=1e-9):
        raise F6TemplateRenderStop(f"replacement text overflowed frozen F6 zone: {zone_id}")


def _mask_intervals_for_row(
    *,
    y: int,
    width: int,
    page_zones: tuple[pymupdf.Rect, ...],
    zoom: float,
) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    for rect in page_zones:
        y0 = max(0, math.floor(rect.y0 * zoom) - _ZONE_MASK_PAD_PIXELS)
        y1 = math.ceil(rect.y1 * zoom) + _ZONE_MASK_PAD_PIXELS
        if not y0 <= y < y1:
            continue
        x0 = max(0, math.floor(rect.x0 * zoom) - _ZONE_MASK_PAD_PIXELS)
        x1 = min(width, math.ceil(rect.x1 * zoom) + _ZONE_MASK_PAD_PIXELS)
        if x0 < x1:
            spans.append((x0, x1))
    if not spans:
        return ()
    spans.sort()
    merged: list[tuple[int, int]] = [spans[0]]
    for start, end in spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return tuple(merged)


def _outside_zone_diff(
    *,
    before_page: pymupdf.Page,
    after_page: pymupdf.Page,
    page_number: int,
    page_zones: tuple[pymupdf.Rect, ...],
) -> F6PageDiffEvidence:
    matrix = pymupdf.Matrix(_RENDER_ZOOM, _RENDER_ZOOM)
    before = before_page.get_pixmap(matrix=matrix, alpha=False)
    after = after_page.get_pixmap(matrix=matrix, alpha=False)
    if (
        before.width != after.width
        or before.height != after.height
        or before.n != after.n
    ):
        raise F6TemplateRenderStop(f"rendered F6 page geometry changed: page {page_number}")

    channels = before.n
    before_samples = memoryview(before.samples)
    after_samples = memoryview(after.samples)
    before_hash = sha256()
    after_hash = sha256()
    changed_pixels = 0
    compared_pixels = 0

    for y in range(before.height):
        masked = _mask_intervals_for_row(
            y=y,
            width=before.width,
            page_zones=page_zones,
            zoom=_RENDER_ZOOM,
        )
        cursor = 0
        for start, end in (*masked, (before.width, before.width)):
            if cursor < start:
                left = (y * before.width + cursor) * channels
                right = (y * before.width + start) * channels
                before_segment = before_samples[left:right]
                after_segment = after_samples[left:right]
                before_hash.update(before_segment)
                after_hash.update(after_segment)
                compared_pixels += start - cursor
                if before_segment != after_segment:
                    for offset in range(0, len(before_segment), channels):
                        if (
                            before_segment[offset : offset + channels]
                            != after_segment[offset : offset + channels]
                        ):
                            changed_pixels += 1
            cursor = max(cursor, end)

    return F6PageDiffEvidence(
        page=page_number,
        width_px=before.width,
        height_px=before.height,
        compared_pixels=compared_pixels,
        changed_pixels=changed_pixels,
        outside_zone_sha256_before=before_hash.hexdigest(),
        outside_zone_sha256_after=after_hash.hexdigest(),
    )


def probe_template_replacement_overflows(
    *,
    document_type: str,
    template_pdf: bytes,
    replacements: Mapping[str, object],
) -> tuple[str, ...]:
    """Return every replacement zone that cannot fit at the source text scale.

    This is a read-only preflight. It uses the same exact template authority,
    source-derived text style and no-scaling rule as the final renderer, but it
    changes no PDF bytes and emits no render authority.
    """

    spec = validate_template_pdf(document_type=document_type, content=template_pdf)
    normalized = _normalize_replacements(spec=spec, replacements=replacements)
    zones = _zone_map(spec)
    document = pymupdf.open(stream=template_pdf, filetype="pdf")
    try:
        overflow: list[str] = []
        for zone_id, text in normalized.items():
            zone = zones[zone_id]
            page_index = _page_index(zone, spec)
            rect = _zone_rect(zone)
            if not _text_fits(
                page=document[page_index],
                rect=rect,
                zone_id=zone_id,
                text=text,
            ):
                overflow.append(zone_id)
        return tuple(overflow)
    finally:
        document.close()


def render_template_pdf(
    *,
    document_type: str,
    template_pdf: bytes,
    replacements: Mapping[str, object],
) -> F6TemplateRenderResult:
    """Render review-only text into exact F6 template zones."""

    spec = validate_template_pdf(document_type=document_type, content=template_pdf)
    normalized = _normalize_replacements(spec=spec, replacements=replacements)
    zones = _zone_map(spec)

    before_doc = pymupdf.open(stream=template_pdf, filetype="pdf")
    working_doc = pymupdf.open(stream=template_pdf, filetype="pdf")
    try:
        for zone_id, text in normalized.items():
            zone = zones[zone_id]
            page_index = _page_index(zone, spec)
            rect = _zone_rect(zone)
            _assert_text_fits(
                page=before_doc[page_index],
                rect=rect,
                zone_id=zone_id,
                text=text,
            )
            _apply_text_zone(
                page=working_doc[page_index],
                rect=rect,
                zone_id=zone_id,
                text=text,
            )
        output_pdf = working_doc.tobytes(garbage=4, deflate=True, clean=True)
    finally:
        working_doc.close()

    after_doc = pymupdf.open(stream=output_pdf, filetype="pdf")
    try:
        if after_doc.page_count != before_doc.page_count:
            raise F6TemplateRenderStop("rendered F6 PDF page count changed")
        evidence: list[F6PageDiffEvidence] = []
        for page_index in range(before_doc.page_count):
            page_zones = tuple(
                _zone_rect(zone)
                for zone in spec.editable_text_zones
                if _page_index(zone, spec) == page_index
            )
            item = _outside_zone_diff(
                before_page=before_doc[page_index],
                after_page=after_doc[page_index],
                page_number=page_index + 1,
                page_zones=page_zones,
            )
            evidence.append(item)
            if item.changed_pixels:
                raise F6TemplateRenderStop(
                    "rendered F6 pixels changed outside declared text zones: "
                    f"page {item.page}, changed_pixels={item.changed_pixels}"
                )
    finally:
        before_doc.close()
        after_doc.close()

    return F6TemplateRenderResult(
        document_type=spec.document_type,
        template_id=spec.template_id,
        source_sha256=sha256(template_pdf).hexdigest(),
        output_sha256=sha256(output_pdf).hexdigest(),
        applied_zone_ids=tuple(normalized),
        page_diff_evidence=tuple(evidence),
        pdf_bytes=output_pdf,
    )


__all__ = [
    "F6PageDiffEvidence",
    "F6TemplateRenderResult",
    "F6TemplateRenderStop",
    "probe_template_replacement_overflows",
    "render_template_pdf",
]
