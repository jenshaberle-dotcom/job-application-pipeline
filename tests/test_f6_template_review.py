from hashlib import sha256
from pathlib import Path

import pymupdf
import pytest

from src.search_intelligence import f6_template_review as review
from src.search_intelligence.f6_template_authority import F6TemplateSpec
from src.search_intelligence.f6_template_renderer import (
    F6PageDiffEvidence,
    F6TemplateRenderResult,
)


def _pdf_with_text(text: str = "Original profile") -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((30, 60), text, fontsize=10)
    payload = doc.tobytes()
    doc.close()
    return payload


def _spec(document_type: str, digest: str, zone_id: str) -> F6TemplateSpec:
    return F6TemplateSpec(
        template_id=f"f6-{document_type}-test",
        document_type=document_type,
        canonical_filename=f"{document_type}.pdf",
        sha256=digest,
        page_count=1,
        page_size_points=((300.0, 400.0),),
        page_format=("test",),
        editable_text_zones=(
            {"id": zone_id, "page": 1, "bbox": [20.0, 40.0, 250.0, 90.0]},
        ),
    )


def _install(root: Path, spec: F6TemplateSpec, payload: bytes) -> None:
    uploads = root / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    (uploads / f"{spec.document_type}-{spec.sha256[:12]}-test.pdf").write_bytes(payload)


def test_review_payload_exposes_zone_text_but_never_private_template_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _pdf_with_text()
    digest = sha256(payload).hexdigest()
    specs = (
        _spec("base_cv", digest, "p1.short_profile"),
        _spec("base_application_letter", digest, "body.paragraph_1"),
    )
    for spec in specs:
        _install(tmp_path, spec, payload)

    monkeypatch.setattr(review, "template_specs", lambda: specs)
    monkeypatch.setattr(
        review,
        "validate_template_pdf",
        lambda *, document_type, content: next(
            spec for spec in specs if spec.document_type == document_type
        ),
    )

    result = review.build_review_payload(root=tmp_path)

    assert result["status"] == "ready"
    assert result["slice"] == "C"
    assert result["private_template_bytes_exposed"] is False
    assert result["human_review_required"] is True
    assert result["submission_authority"] is False
    templates = result["templates"]
    assert len(templates) == 2
    assert templates[0]["zones"][0]["source_text"] == "Original profile"


def test_review_export_requires_both_exact_document_types(tmp_path: Path) -> None:
    with pytest.raises(
        review.F6TemplateReviewStop,
        match="requires exactly base_cv and base_application_letter",
    ):
        review.render_review_package(
            root=tmp_path,
            replacements_by_document={"base_cv": {}},
        )


def test_review_export_passes_only_declared_operator_edits_to_slice_b_renderer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _pdf_with_text()
    digest = sha256(payload).hexdigest()
    specs = (
        _spec("base_cv", digest, "p1.short_profile"),
        _spec("base_application_letter", digest, "body.paragraph_1"),
    )
    for spec in specs:
        _install(tmp_path, spec, payload)

    monkeypatch.setattr(review, "template_specs", lambda: specs)
    monkeypatch.setattr(
        review,
        "validate_template_pdf",
        lambda *, document_type, content: next(
            spec for spec in specs if spec.document_type == document_type
        ),
    )

    calls: list[tuple[str, dict[str, object]]] = []

    def fake_render(
        *,
        document_type: str,
        template_pdf: bytes,
        replacements: dict[str, object],
    ) -> F6TemplateRenderResult:
        calls.append((document_type, dict(replacements)))
        spec = next(item for item in specs if item.document_type == document_type)
        evidence = F6PageDiffEvidence(
            page=1,
            width_px=300,
            height_px=400,
            compared_pixels=100,
            changed_pixels=0,
            outside_zone_sha256_before="a" * 64,
            outside_zone_sha256_after="a" * 64,
        )
        return F6TemplateRenderResult(
            document_type=document_type,
            template_id=spec.template_id,
            source_sha256=spec.sha256,
            output_sha256="b" * 64,
            applied_zone_ids=tuple(replacements),
            page_diff_evidence=(evidence,),
            pdf_bytes=b"%PDF-review",
        )

    monkeypatch.setattr(review, "render_template_pdf", fake_render)

    result = review.render_review_package(
        root=tmp_path,
        replacements_by_document={
            "base_cv": {"p1.short_profile": "Edited profile"},
            "base_application_letter": {"body.paragraph_1": "Edited opening"},
        },
    )

    assert calls == [
        ("base_cv", {"p1.short_profile": "Edited profile"}),
        ("base_application_letter", {"body.paragraph_1": "Edited opening"}),
    ]
    assert len(result) == 2
    assert all(item.render_evidence["outside_zone_pixel_identity"] is True for item in result)


def test_review_export_rejects_undeclared_zone_before_renderer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _pdf_with_text()
    digest = sha256(payload).hexdigest()
    specs = (
        _spec("base_cv", digest, "p1.short_profile"),
        _spec("base_application_letter", digest, "body.paragraph_1"),
    )
    for spec in specs:
        _install(tmp_path, spec, payload)

    monkeypatch.setattr(review, "template_specs", lambda: specs)
    monkeypatch.setattr(
        review,
        "validate_template_pdf",
        lambda *, document_type, content: next(
            spec for spec in specs if spec.document_type == document_type
        ),
    )

    with pytest.raises(review.F6TemplateReviewStop, match="undeclared F6 text zone"):
        review.render_review_package(
            root=tmp_path,
            replacements_by_document={
                "base_cv": {"not.allowed": "no"},
                "base_application_letter": {},
            },
        )



def test_combined_review_package_is_one_letter_plus_cv_pdf_with_visual_identity() -> None:
    letter = _pdf_with_text("Letter")
    cv = _pdf_with_text("CV")
    rendered = (
        review.F6RenderedReviewDocument(
            document_type="base_cv",
            canonical_filename="cv.pdf",
            pdf_bytes=cv,
            render_evidence={"outside_zone_pixel_identity": True},
        ),
        review.F6RenderedReviewDocument(
            document_type="base_application_letter",
            canonical_filename="letter.pdf",
            pdf_bytes=letter,
            render_evidence={"outside_zone_pixel_identity": True},
        ),
    )

    package = review.combine_review_package(rendered)

    assert package.component_order == ("base_application_letter", "base_cv")
    assert package.page_count == 2
    assert len(package.page_identity) == 2
    assert all(item["visual_identity"] is True for item in package.page_identity)
    assert package.sha256 == sha256(package.pdf_bytes).hexdigest()

    doc = pymupdf.open(stream=package.pdf_bytes, filetype="pdf")
    try:
        assert doc.page_count == 2
        assert "Letter" in doc[0].get_text()
        assert "CV" in doc[1].get_text()
    finally:
        doc.close()


def test_review_fit_preflight_prefixes_document_and_zone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _pdf_with_text()
    digest = sha256(payload).hexdigest()
    specs = (
        _spec("base_cv", digest, "p1.short_profile"),
        _spec("base_application_letter", digest, "salutation"),
    )
    for spec in specs:
        _install(tmp_path, spec, payload)

    monkeypatch.setattr(review, "template_specs", lambda: specs)
    monkeypatch.setattr(
        review,
        "validate_template_pdf",
        lambda *, document_type, content: next(
            spec for spec in specs if spec.document_type == document_type
        ),
    )
    monkeypatch.setattr(
        review,
        "probe_template_replacement_overflows",
        lambda *, document_type, template_pdf, replacements: (
            ("salutation",)
            if document_type == "base_application_letter"
            else ()
        ),
    )

    result = review.probe_review_replacement_overflows(
        root=tmp_path,
        replacements_by_document={
            "base_cv": {"p1.short_profile": "Fits"},
            "base_application_letter": {"salutation": "Too long"},
        },
    )

    assert result == ("base_application_letter:salutation",)
