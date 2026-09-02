"""Bind current Product V1 Top-5 truth to the application-generation context.

This module is intentionally side-effect free. Runtime callers supply one authoritative
Top-5 row, fetched employer-origin detail text, the private Candidate Fact profile/facts,
and approved base-document rows plus a local content loader. The result is the existing
source-grounded :class:`ProductV1ApplicationContext`; no provider or application action
is performed here.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable, Mapping, Sequence
from urllib.parse import unquote, urlparse

from src.search_intelligence.private_application_source_text import (
    PrivateApplicationSourceTextError,
    extract_private_application_source_text,
)
from src.search_intelligence.product_v1_application_context import (
    ApplicationSourceDocumentSnapshot,
    ApplicationTargetSnapshot,
    CandidateFactSnapshot,
    ProductV1ApplicationContext,
    build_product_v1_application_context,
)


DocumentLoader = Callable[[str], str]
_REQUIRED_DOCUMENT_TYPES = ("base_cv", "base_application_letter")


class ApplicationWorkspaceStop(RuntimeError):
    """Raised when runtime evidence cannot safely bind an application workspace."""


def _required_text(row: Mapping[str, object], key: str) -> str:
    value = str(row.get(key) or "").strip()
    if not value:
        raise ApplicationWorkspaceStop(f"{key} is required")
    return value


def _as_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ApplicationWorkspaceStop(f"invalid date value: {text}") from exc


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value if str(item).strip())
    return ()


def local_document_loader(
    *,
    private_root: Path | None = None,
) -> DocumentLoader:
    """Return a fail-closed loader for local private base-document references.

    Supported references are absolute/relative filesystem paths, ``file://`` URIs,
    and ``local://`` references resolved under ``private_root``. UTF-8 text and
    text-bearing PDF files are supported. Network and opaque operator URIs are never
    dereferenced.
    """

    root = private_root.expanduser().resolve() if private_root is not None else None

    def load(source_reference: str) -> str:
        raw = source_reference.strip()
        if not raw:
            raise ApplicationWorkspaceStop("application source reference is empty")

        parsed = urlparse(raw)
        if parsed.scheme == "file":
            if parsed.netloc not in {"", "localhost"}:
                raise ApplicationWorkspaceStop("remote file URI is not allowed")
            path = Path(unquote(parsed.path)).expanduser()
        elif parsed.scheme == "local":
            if root is None:
                raise ApplicationWorkspaceStop(
                    "PRODUCT_V1_PRIVATE_DOCUMENT_ROOT is required for local:// references"
                )
            relative = (parsed.netloc + parsed.path).lstrip("/")
            path = root / relative
        elif parsed.scheme:
            raise ApplicationWorkspaceStop(
                f"unsupported application source reference scheme: {parsed.scheme}"
            )
        else:
            candidate = Path(raw).expanduser()
            path = candidate if candidate.is_absolute() else (root / candidate if root else candidate)

        resolved = path.resolve()
        if root is not None and root not in {resolved, *resolved.parents}:
            raise ApplicationWorkspaceStop("application source escaped private document root")
        try:
            return extract_private_application_source_text(resolved)
        except PrivateApplicationSourceTextError as exc:
            raise ApplicationWorkspaceStop(str(exc)) from exc

    return load


def _target_snapshot(
    row: Mapping[str, object],
    *,
    detail_text: str,
) -> ApplicationTargetSnapshot:
    try:
        silver_job_id = int(row.get("silver_job_id") or 0)
        product_rank = int(row.get("product_rank") or 0)
    except (TypeError, ValueError) as exc:
        raise ApplicationWorkspaceStop("invalid Top-5 job identity") from exc
    return ApplicationTargetSnapshot(
        silver_job_id=silver_job_id,
        product_rank=product_rank,
        title=_required_text(row, "title"),
        company_name=_required_text(row, "company_name"),
        source_url=_required_text(row, "source_url"),
        canonical_source_type=_required_text(row, "canonical_source_type"),
        product_readiness_status=_required_text(row, "product_readiness_status"),
        origin_validation_status=_required_text(row, "origin_validation_status"),
        activity_status=_required_text(row, "activity_status"),
        hard_filter_status=_required_text(row, "hard_filter_status"),
        detail_text=detail_text,
    )


def _fact_snapshots(rows: Sequence[Mapping[str, object]]) -> tuple[CandidateFactSnapshot, ...]:
    result: list[CandidateFactSnapshot] = []
    for row in rows:
        result.append(
            CandidateFactSnapshot(
                fact_key=_required_text(row, "fact_key"),
                category=_required_text(row, "category"),
                evidence_class=_required_text(row, "evidence_class"),
                approval_status=_required_text(row, "approval_status"),
                statement=_required_text(row, "statement"),
                capability_tags=_string_tuple(row.get("capability_tags")),
                limitations=_string_tuple(row.get("limitations")),
                valid_from=_as_date(row.get("valid_from")),
                valid_until=_as_date(row.get("valid_until")),
            )
        )
    return tuple(result)


def _document_snapshots(
    rows: Sequence[Mapping[str, object]],
    *,
    load_document: DocumentLoader,
) -> tuple[ApplicationSourceDocumentSnapshot, ...]:
    selected: dict[str, Mapping[str, object]] = {}
    for row in rows:
        document_type = str(row.get("document_type") or "").strip()
        if document_type not in _REQUIRED_DOCUMENT_TYPES:
            continue
        if document_type in selected:
            raise ApplicationWorkspaceStop(f"duplicate approved {document_type} source")
        selected[document_type] = row

    snapshots: list[ApplicationSourceDocumentSnapshot] = []
    for document_type in _REQUIRED_DOCUMENT_TYPES:
        row = selected.get(document_type)
        if row is None:
            continue
        source_reference = _required_text(row, "source_reference")
        snapshots.append(
            ApplicationSourceDocumentSnapshot(
                document_type=document_type,
                source_label=_required_text(row, "source_label"),
                source_reference=source_reference,
                content_sha256=_required_text(row, "content_sha256"),
                content=load_document(source_reference),
                status=_required_text(row, "status"),
            )
        )
    return tuple(snapshots)


def build_application_workspace_context(
    *,
    top_job_row: Mapping[str, object],
    detail_text: str,
    profile_row: Mapping[str, object] | None,
    fact_rows: Sequence[Mapping[str, object]],
    document_rows: Sequence[Mapping[str, object]],
    load_document: DocumentLoader,
    as_of_date: date,
) -> ProductV1ApplicationContext:
    """Build the canonical source-grounded context from current runtime evidence."""

    if profile_row is None:
        profile_status = "missing"
        profile_sha256 = ""
    else:
        profile_status = str(profile_row.get("status") or "missing")
        profile_sha256 = str(profile_row.get("payload_sha256") or "")

    target = _target_snapshot(top_job_row, detail_text=detail_text)
    facts = _fact_snapshots(fact_rows)
    documents = _document_snapshots(document_rows, load_document=load_document)
    return build_product_v1_application_context(
        target=target,
        candidate_profile_status=profile_status,
        candidate_profile_sha256=profile_sha256,
        candidate_facts=facts,
        source_documents=documents,
        as_of_date=as_of_date,
    )


__all__ = [
    "ApplicationWorkspaceStop",
    "DocumentLoader",
    "build_application_workspace_context",
    "local_document_loader",
]
