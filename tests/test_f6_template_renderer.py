from __future__ import annotations

from hashlib import sha256

import pymupdf
import pytest

from src.search_intelligence import f6_template_renderer as renderer
from src.search_intelligence.f6_template_authority import F6TemplateSpec


def _template_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page(width=300, height=400)
    page.draw_rect(pymupdf.Rect(10, 10, 290, 390), color=(0, 0, 1), width=2)
    page.draw_line(
        pymupdf.Point(0, 200),
        pymupdf.Point(300, 200),
        color=(1, 0, 0),
        width=3,
    )
    page.insert_textbox(
        pymupdf.Rect(40, 60, 260, 105),
        "ORIGINAL TEXT",
        fontsize=11,
    )
    payload = document.tobytes()
    document.close()
    return payload


def _spec(payload: bytes) -> F6TemplateSpec:
    return F6TemplateSpec(
        template_id="f6-synthetic-renderer-fixture",
        document_type="base_application_letter",
        canonical_filename="synthetic.pdf",
        sha256=sha256(payload).hexdigest(),
        page_count=1,
        page_size_points=((300.0, 400.0),),
        page_format=("fixture",),
        editable_text_zones=(
            {
                "id": "body.paragraph_1",
                "page": 1,
                "bbox": [35.0, 55.0, 265.0, 120.0],
            },
        ),
    )


def _bind_exact_authority(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
) -> F6TemplateSpec:
    spec = _spec(payload)

    def validate(*, document_type: str, content: bytes) -> F6TemplateSpec:
        assert document_type == spec.document_type
        assert sha256(content).hexdigest() == spec.sha256
        return spec

    monkeypatch.setattr(renderer, "validate_template_pdf", validate)
    return spec


def test_renderer_changes_only_declared_text_zone_and_emits_pixel_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _template_pdf()
    spec = _bind_exact_authority(monkeypatch, source)

    result = renderer.render_template_pdf(
        document_type=spec.document_type,
        template_pdf=source,
        replacements={"body.paragraph_1": "Neuer F6 Text für die Prüfung."},
    )

    assert result.source_sha256 == spec.sha256
    assert result.output_sha256 != result.source_sha256
    assert result.applied_zone_ids == ("body.paragraph_1",)
    assert result.outside_zone_pixel_identity is True
    assert len(result.page_diff_evidence) == 1
    evidence = result.page_diff_evidence[0]
    assert evidence.changed_pixels == 0
    assert evidence.compared_pixels > 0
    assert evidence.outside_zone_sha256_before == evidence.outside_zone_sha256_after

    rendered = pymupdf.open(stream=result.pdf_bytes, filetype="pdf")
    try:
        text = rendered[0].get_text()
        drawings = rendered[0].get_drawings()
    finally:
        rendered.close()
    assert "Neuer F6 Text" in text
    assert "ORIGINAL TEXT" not in text
    assert drawings, "immutable vector graphics disappeared during text-only redaction"

    public = result.public_payload()
    assert public["status"] == "rendered_for_review"
    assert public["outside_zone_pixel_identity"] is True
    assert public["human_review_required"] is True
    assert public["application_authority"] is False
    assert public["submission_authority"] is False
    assert public["send_authority"] is False


def test_renderer_rejects_undeclared_zone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _template_pdf()
    spec = _bind_exact_authority(monkeypatch, source)

    with pytest.raises(
        renderer.F6TemplateRenderStop,
        match="undeclared F6 text zone",
    ):
        renderer.render_template_pdf(
            document_type=spec.document_type,
            template_pdf=source,
            replacements={"outside.authority": "must fail"},
        )


def test_renderer_fails_closed_on_text_overflow_without_scaling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _template_pdf()
    spec = _bind_exact_authority(monkeypatch, source)

    with pytest.raises(
        renderer.F6TemplateRenderStop,
        match="does not fit frozen F6 zone without scaling",
    ):
        renderer.render_template_pdf(
            document_type=spec.document_type,
            template_pdf=source,
            replacements={"body.paragraph_1": "zu viel Text " * 180},
        )


def test_outside_zone_diff_detects_graphic_mutation() -> None:
    source = _template_pdf()
    spec = _spec(source)
    before = pymupdf.open(stream=source, filetype="pdf")
    tampered = pymupdf.open(stream=source, filetype="pdf")
    try:
        tampered[0].draw_rect(
            pymupdf.Rect(270, 300, 290, 320),
            color=(0, 1, 0),
            fill=(0, 1, 0),
        )
        tampered_bytes = tampered.tobytes()
    finally:
        tampered.close()

    after = pymupdf.open(stream=tampered_bytes, filetype="pdf")
    try:
        zone_rects = tuple(
            renderer._zone_rect(zone) for zone in spec.editable_text_zones
        )
        evidence = renderer._outside_zone_diff(
            before_page=before[0],
            after_page=after[0],
            page_number=1,
            page_zones=zone_rects,
        )
    finally:
        before.close()
        after.close()

    assert evidence.changed_pixels > 0
    assert evidence.outside_zone_sha256_before != evidence.outside_zone_sha256_after


def test_fit_preflight_reports_overflow_without_mutating_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _template_pdf()
    spec = _bind_exact_authority(monkeypatch, source)

    fitting = renderer.probe_template_replacement_overflows(
        document_type=spec.document_type,
        template_pdf=source,
        replacements={"body.paragraph_1": "Kurzer Text."},
    )
    overflowing = renderer.probe_template_replacement_overflows(
        document_type=spec.document_type,
        template_pdf=source,
        replacements={"body.paragraph_1": "zu viel Text " * 180},
    )

    assert fitting == ()
    assert overflowing == ("body.paragraph_1",)
    assert sha256(source).hexdigest() == spec.sha256



def test_render_uses_same_pristine_source_style_as_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _template_pdf()
    spec = _bind_exact_authority(monkeypatch, source)

    calls: list[bool] = []

    def source_style(page: pymupdf.Page, rect: pymupdf.Rect):
        has_source_text = bool(page.get_textbox(rect).strip())
        calls.append(has_source_text)
        # A post-redaction style lookup would hit the deliberately huge fallback
        # and make the final render diverge from the successful preflight.
        return (7.0, "#000000", False) if has_source_text else (18.0, "#000000", False)

    monkeypatch.setattr(renderer, "_source_text_style", source_style)
    replacement = "Präziser Kompetenztext mit mehreren kompakten Begriffen."

    assert renderer.probe_template_replacement_overflows(
        document_type=spec.document_type,
        template_pdf=source,
        replacements={"body.paragraph_1": replacement},
    ) == ()

    result = renderer.render_template_pdf(
        document_type=spec.document_type,
        template_pdf=source,
        replacements={"body.paragraph_1": replacement},
    )

    assert result.outside_zone_pixel_identity is True
    assert calls
    assert all(calls), "renderer must never derive replacement style after redaction"
