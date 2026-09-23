from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.search_intelligence.f6_template_authority import (
    F6TemplateAuthorityStop,
    authority_status,
    template_spec,
    template_specs,
    validate_template_pdf,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "application_templates" / "f6_template_authority_v1.json"

LETTER_SHA = "e533e27c8bc4ac04b64e29e8d91dcfd134d23af075f76ec179e0d9d0ab1410c8"
CV_SHA = "8f67040b6ef9248e734a18e46df87fa786f33c3c8f605785baf7ad324432e041"

LEGACY_PATHS = (
    ROOT / "src" / "search_intelligence" / "product_v1_application_document_export.py",
    ROOT / "src" / "search_intelligence" / "product_v1_application_document_package.py",
    ROOT / "frontend" / "control-center" / "src" / "application-package-downloads.css",
    ROOT / "tests" / "test_product_v1_application_document_export.py",
    ROOT / "tests" / "test_product_v1_application_document_package.py",
)


def test_f6_authority_contains_exactly_the_two_operator_approved_private_templates() -> None:
    specs = {spec.document_type: spec for spec in template_specs()}

    assert set(specs) == {"base_cv", "base_application_letter"}

    letter = specs["base_application_letter"]
    assert letter.template_id == "f6-application-letter-hornetsecurity-2026-09-17-v1"
    assert letter.canonical_filename == "Hornetsecurity_Jens_Haberle_Anschreiben.pdf"
    assert letter.sha256 == LETTER_SHA
    assert letter.page_count == 1
    assert letter.page_size_points == ((612.0, 792.0),)
    assert letter.page_format == ("letter",)

    cv = specs["base_cv"]
    assert cv.template_id == "f6-cv-hornetsecurity-2026-09-17-v1"
    assert cv.canonical_filename == "Hornetsecurity_Jens_Haberle_Lebenslauf.pdf"
    assert cv.sha256 == CV_SHA
    assert cv.page_count == 2
    assert cv.page_size_points == ((595.32, 841.92), (595.32, 841.92))
    assert cv.page_format == ("A4", "A4")


def test_editable_zones_are_explicit_unique_and_inside_frozen_page_geometry() -> None:
    for spec in template_specs():
        zone_ids: set[str] = set()
        for zone in spec.editable_text_zones:
            zone_id = str(zone["id"])
            assert zone_id not in zone_ids
            zone_ids.add(zone_id)

            page_number = int(zone["page"])
            assert 1 <= page_number <= spec.page_count
            x0, y0, x1, y1 = [float(value) for value in zone["bbox"]]
            width, height = spec.page_size_points[page_number - 1]
            assert 0 <= x0 < x1 <= width
            assert 0 <= y0 < y1 <= height
        assert zone_ids


def test_authority_status_is_ready_only_for_both_exact_hashes() -> None:
    ready = authority_status(
        {
            "base_cv": CV_SHA,
            "base_application_letter": LETTER_SHA,
        }
    )
    assert ready["status"] == "ready"
    assert ready["layout_policy"] == "pixel_bound_text_zones_only"
    assert ready["legacy_template_authority"] is False
    assert ready["automatic_submit_or_send"] is False
    assert ready["human_review_required"] is True
    assert all(item["exact_authority_match"] for item in ready["templates"])

    blocked = authority_status(
        {
            "base_cv": "0" * 64,
            "base_application_letter": LETTER_SHA,
        }
    )
    assert blocked["status"] == "blocked"
    by_type = {item["document_type"]: item for item in blocked["templates"]}
    assert by_type["base_cv"]["exact_authority_match"] is False
    assert by_type["base_application_letter"]["exact_authority_match"] is True


def test_non_authority_pdf_is_rejected_before_it_can_become_template_truth() -> None:
    with pytest.raises(F6TemplateAuthorityStop, match="not the frozen F6 template"):
        validate_template_pdf(document_type="base_cv", content=b"%PDF-1.7\nnot-authority")


def test_manifest_keeps_private_template_bytes_out_of_public_repo() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    policy = payload["authority_policy"]

    assert policy["binary_storage"] == "private_local_only"
    assert policy["public_repo_contains_template_bytes"] is False
    assert policy["exact_source_sha256_required"] is True
    assert policy["layout_mutation_allowed"] is False
    assert policy["text_zone_mutation_only"] is True
    assert policy["human_review_required"] is True
    assert policy["automatic_submit_or_send"] is False


def test_legacy_generic_template_renderer_is_physically_absent() -> None:
    for path in LEGACY_PATHS:
        assert not path.exists(), f"legacy F6 regression path exists: {path.relative_to(ROOT)}"


def test_active_f6_surfaces_do_not_reintroduce_legacy_generic_export_tokens() -> None:
    paths = (
        ROOT / "scripts" / "product_v1_application_workspace_runtime_quality.py",
        ROOT / "frontend" / "control-center" / "src" / "DemoApplicationWorkspace.tsx",
        ROOT / "frontend" / "control-center" / "src" / "ApplicationSourceUpload.tsx",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    for forbidden in (
        "render_application_document_bundle",
        "build_application_document_package_payload",
        "ready_for_download",
        'key === "cv_docx"',
        'key === "application_zip"',
        "use_as_base_document",
    ):
        assert forbidden not in combined

    assert "install_f6_authority_template" in combined
    assert "f6_template_authority_v1" in combined
    assert "legacy_generic_document_export" in combined


def test_expected_template_ids_are_stable_by_document_type() -> None:
    assert template_spec("base_cv").sha256 == CV_SHA
    assert template_spec("base_application_letter").sha256 == LETTER_SHA
    with pytest.raises(F6TemplateAuthorityStop, match="unsupported F6"):
        template_spec("portfolio")
