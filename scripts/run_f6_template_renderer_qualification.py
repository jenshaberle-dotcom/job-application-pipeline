"""Qualify F6 Slice B against the exact locally installed private templates.

This is an operator proof, not a document-export path. It renders one short
qualification marker into one declared text zone of each exact private template,
verifies pixel identity outside every declared zone, reports only hashes/evidence,
and discards the rendered PDF bytes.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.product_v1_local_document_intake import private_document_root
from src.search_intelligence.f6_template_authority import (
    F6TemplateAuthorityStop,
    F6TemplateSpec,
    template_specs,
    validate_template_pdf,
)
from src.search_intelligence.f6_template_renderer import (
    F6TemplateRenderStop,
    render_template_pdf,
)


class F6RendererQualificationStop(RuntimeError):
    """Fail closed when the local exact-template renderer proof cannot complete."""


_QUALIFICATION_ZONES = {
    "base_application_letter": "body.paragraph_1",
    "base_cv": "p1.short_profile",
}
_QUALIFICATION_TEXT = "F6 renderer qualification — review only"


def _installed_template_path(*, root: Path, spec: F6TemplateSpec) -> Path:
    upload_root = root / "uploads"
    candidates = tuple(
        sorted(
            upload_root.glob(
                f"{spec.document_type}-{spec.sha256[:12]}-*.pdf"
            )
        )
    )
    if len(candidates) != 1:
        raise F6RendererQualificationStop(
            "expected exactly one installed exact F6 template for "
            f"{spec.document_type}, found {len(candidates)}"
        )
    return candidates[0]


def qualify_installed_templates(
    *,
    root: Path | None = None,
) -> dict[str, object]:
    private_root = (root or private_document_root()).expanduser().resolve()
    proofs: list[dict[str, object]] = []

    for spec in template_specs():
        zone_id = _QUALIFICATION_ZONES.get(spec.document_type)
        if zone_id is None:
            raise F6RendererQualificationStop(
                f"no F6 renderer qualification zone for {spec.document_type}"
            )
        declared = {str(zone["id"]) for zone in spec.editable_text_zones}
        if zone_id not in declared:
            raise F6RendererQualificationStop(
                f"qualification zone is not declared by F6 authority: {zone_id}"
            )

        path = _installed_template_path(root=private_root, spec=spec)
        template_pdf = path.read_bytes()
        try:
            validate_template_pdf(
                document_type=spec.document_type,
                content=template_pdf,
            )
            result = render_template_pdf(
                document_type=spec.document_type,
                template_pdf=template_pdf,
                replacements={zone_id: _QUALIFICATION_TEXT},
            )
        except (F6TemplateAuthorityStop, F6TemplateRenderStop) as exc:
            raise F6RendererQualificationStop(str(exc)) from exc

        if not result.outside_zone_pixel_identity:
            raise F6RendererQualificationStop(
                f"outside-zone pixel identity failed for {spec.document_type}"
            )
        proofs.append(
            result.public_payload()
            | {
                "qualification_zone": zone_id,
                "private_template_path_disclosed": False,
                "rendered_pdf_persisted": False,
            }
        )

    if {str(item["document_type"]) for item in proofs} != set(_QUALIFICATION_ZONES):
        raise F6RendererQualificationStop(
            "F6 renderer qualification did not cover exactly both template types"
        )

    return {
        "schema": "job_application_pipeline.f6_template_renderer_qualification.v1",
        "status": "qualified",
        "campaign": "F6",
        "slice": "B",
        "template_count": len(proofs),
        "proofs": proofs,
        "private_template_bytes_exposed": False,
        "rendered_pdf_persisted": False,
        "database_reads": 0,
        "database_writes": 0,
        "provider_requests": 0,
        "network_requests": 0,
        "application_actions": 0,
        "submission_actions": 0,
        "send_actions": 0,
        "human_review_required": True,
    }


def main() -> int:
    try:
        payload = qualify_installed_templates()
    except (F6RendererQualificationStop, OSError) as exc:
        print("F6_TEMPLATE_RENDERER_QUALIFICATION=BLOCKED")
        print(f"REASON={type(exc).__name__}: {exc}")
        return 2

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print("F6_TEMPLATE_RENDERER_QUALIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
