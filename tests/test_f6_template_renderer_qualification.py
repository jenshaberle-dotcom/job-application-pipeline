from __future__ import annotations

from pathlib import Path

import pytest

from scripts import run_f6_template_renderer_qualification as qualification
from src.search_intelligence.f6_template_authority import F6TemplateSpec


def _spec(document_type: str, sha256_value: str) -> F6TemplateSpec:
    zone_id = (
        "body.paragraph_1"
        if document_type == "base_application_letter"
        else "p1.short_profile"
    )
    return F6TemplateSpec(
        template_id=f"fixture-{document_type}",
        document_type=document_type,
        canonical_filename=f"{document_type}.pdf",
        sha256=sha256_value,
        page_count=1,
        page_size_points=((300.0, 400.0),),
        page_format=("fixture",),
        editable_text_zones=(
            {"id": zone_id, "page": 1, "bbox": [10.0, 10.0, 200.0, 100.0]},
        ),
    )


def test_installed_template_path_is_exact_hash_prefix_and_unique(tmp_path: Path) -> None:
    spec = _spec("base_cv", "a" * 64)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    target = uploads / f"base_cv-{spec.sha256[:12]}-base_cv.pdf"
    target.write_bytes(b"%PDF-fixture")

    assert qualification._installed_template_path(root=tmp_path, spec=spec) == target

    duplicate = uploads / f"base_cv-{spec.sha256[:12]}-duplicate.pdf"
    duplicate.write_bytes(b"%PDF-fixture")
    with pytest.raises(
        qualification.F6RendererQualificationStop,
        match="expected exactly one installed exact F6 template",
    ):
        qualification._installed_template_path(root=tmp_path, spec=spec)


def test_qualification_contract_has_no_persistence_or_action_authority(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    letter = _spec("base_application_letter", "b" * 64)
    cv = _spec("base_cv", "c" * 64)
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    for spec in (letter, cv):
        (
            uploads
            / f"{spec.document_type}-{spec.sha256[:12]}-{spec.canonical_filename}"
        ).write_bytes(b"%PDF-fixture")

    monkeypatch.setattr(qualification, "template_specs", lambda: (letter, cv))
    monkeypatch.setattr(qualification, "validate_template_pdf", lambda **_: letter)

    class Result:
        outside_zone_pixel_identity = True

        def __init__(self, document_type: str) -> None:
            self.document_type = document_type

        def public_payload(self) -> dict[str, object]:
            return {
                "status": "rendered_for_review",
                "document_type": self.document_type,
                "outside_zone_pixel_identity": True,
                "application_authority": False,
                "submission_authority": False,
                "send_authority": False,
            }

    monkeypatch.setattr(
        qualification,
        "render_template_pdf",
        lambda *, document_type, template_pdf, replacements: Result(document_type),
    )

    payload = qualification.qualify_installed_templates(root=tmp_path)

    assert payload["status"] == "qualified"
    assert payload["template_count"] == 2
    assert payload["rendered_pdf_persisted"] is False
    assert payload["private_template_bytes_exposed"] is False
    assert payload["database_reads"] == 0
    assert payload["database_writes"] == 0
    assert payload["provider_requests"] == 0
    assert payload["network_requests"] == 0
    assert payload["application_actions"] == 0
    assert payload["submission_actions"] == 0
    assert payload["send_actions"] == 0
