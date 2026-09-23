"""F6 template authority for pixel-bound application documents.

The canonical template binaries stay private/local.  Public repository truth contains
only exact binary hashes, immutable page geometry and the text zones that may later
be changed.  Any other PDF is rejected before it can become an approved application
source.

This module grants no rendering, drafting, approval, submission or send authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from typing import Mapping

from pypdf import PdfReader


_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "application_templates"
    / "f6_template_authority_v1.json"
)


class F6TemplateAuthorityStop(ValueError):
    """Fail closed when a PDF does not match the frozen F6 template authority."""


@dataclass(frozen=True)
class F6TemplateSpec:
    template_id: str
    document_type: str
    canonical_filename: str
    sha256: str
    page_count: int
    page_size_points: tuple[tuple[float, float], ...]
    page_format: tuple[str, ...]
    editable_text_zones: tuple[Mapping[str, object], ...]

    def public_payload(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "document_type": self.document_type,
            "canonical_filename": self.canonical_filename,
            "sha256": self.sha256,
            "page_count": self.page_count,
            "page_size_points": [list(item) for item in self.page_size_points],
            "page_format": list(self.page_format),
            "editable_text_zone_ids": [
                str(zone["id"]) for zone in self.editable_text_zones
            ],
            "editable_text_zone_count": len(self.editable_text_zones),
            "layout_mutation_allowed": False,
            "text_zone_mutation_only": True,
            "binary_storage": "private_local_only",
        }


def _load_manifest() -> Mapping[str, object]:
    payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "job_application_pipeline.f6_template_authority.v1":
        raise RuntimeError("unexpected F6 template authority schema")
    return payload


def template_specs() -> tuple[F6TemplateSpec, ...]:
    payload = _load_manifest()
    raw_templates = payload.get("templates")
    if not isinstance(raw_templates, list) or len(raw_templates) != 2:
        raise RuntimeError("F6 authority must contain exactly two templates")
    result: list[F6TemplateSpec] = []
    for item in raw_templates:
        if not isinstance(item, Mapping):
            raise RuntimeError("F6 template entry must be an object")
        result.append(
            F6TemplateSpec(
                template_id=str(item["template_id"]),
                document_type=str(item["document_type"]),
                canonical_filename=str(item["canonical_filename"]),
                sha256=str(item["sha256"]),
                page_count=int(item["page_count"]),
                page_size_points=tuple(
                    (float(pair[0]), float(pair[1]))
                    for pair in item["page_size_points"]  # type: ignore[index]
                ),
                page_format=tuple(str(value) for value in item["page_format"]),  # type: ignore[index]
                editable_text_zones=tuple(item["editable_text_zones"]),  # type: ignore[arg-type,index]
            )
        )
    return tuple(result)


def template_spec(document_type: str) -> F6TemplateSpec:
    matches = [spec for spec in template_specs() if spec.document_type == document_type]
    if len(matches) != 1:
        raise F6TemplateAuthorityStop(
            f"unsupported F6 application template type: {document_type}"
        )
    return matches[0]


def validate_template_pdf(
    *,
    document_type: str,
    content: bytes,
) -> F6TemplateSpec:
    spec = template_spec(document_type)
    actual_sha = sha256(content).hexdigest()
    if actual_sha != spec.sha256:
        raise F6TemplateAuthorityStop(
            f"{document_type} is not the frozen F6 template "
            f"(expected sha256 {spec.sha256}, got {actual_sha})"
        )
    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:
        raise F6TemplateAuthorityStop("F6 template PDF cannot be parsed") from exc
    if len(reader.pages) != spec.page_count:
        raise F6TemplateAuthorityStop(
            f"{document_type} page count drifted from frozen authority"
        )
    actual_sizes: list[tuple[float, float]] = []
    for page in reader.pages:
        box = page.mediabox
        actual_sizes.append((round(float(box.width), 2), round(float(box.height), 2)))
    expected_sizes = [
        (round(width, 2), round(height, 2))
        for width, height in spec.page_size_points
    ]
    if actual_sizes != expected_sizes:
        raise F6TemplateAuthorityStop(
            f"{document_type} page geometry drifted from frozen authority"
        )
    return spec


def authority_status(
    approved_hashes: Mapping[str, str],
) -> dict[str, object]:
    templates = []
    ready = True
    for spec in template_specs():
        approved = str(approved_hashes.get(spec.document_type) or "")
        exact = approved == spec.sha256
        ready = ready and exact
        templates.append(
            spec.public_payload()
            | {
                "approved_sha256": approved or None,
                "exact_authority_match": exact,
            }
        )
    return {
        "schema": "job_application_pipeline.f6_template_authority_status.v1",
        "campaign": "F6",
        "status": "ready" if ready else "blocked",
        "templates": templates,
        "layout_policy": "pixel_bound_text_zones_only",
        "legacy_template_authority": False,
        "automatic_submit_or_send": False,
        "human_review_required": True,
    }


__all__ = [
    "F6TemplateAuthorityStop",
    "F6TemplateSpec",
    "authority_status",
    "template_spec",
    "template_specs",
    "validate_template_pdf",
]
