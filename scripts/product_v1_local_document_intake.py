"""Local-only browser intake for Product V1 base application documents.

The browser sends a PDF to the local demo server. The file is validated and stored
under the private application-document root; PostgreSQL receives only the existing
application_source_documents metadata contract. No document body is persisted to the
DB and no network/provider/LLM request is performed.
"""
from __future__ import annotations

import base64
import binascii
from hashlib import sha256
import os
from pathlib import Path
import re
from typing import Mapping

from scripts.import_private_application_source_documents import (
    DOCUMENT_TYPES,
    apply_documents,
    build_document,
    build_plan,
    connect,
    ensure_schema,
    load_current_approved,
)
from src.search_intelligence.private_application_source_text import (
    extract_private_application_source_text,
)


MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class LocalDocumentIntakeStop(ValueError):
    """Raised when browser-supplied local document input is unsafe or invalid."""


def private_document_root() -> Path:
    raw = os.environ.get("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", "").strip()
    return Path(raw or "private_application_sources").expanduser().resolve()


def _required_text(payload: Mapping[str, object], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise LocalDocumentIntakeStop(f"{key} is required")
    return value


def parse_upload_payload(payload: object) -> tuple[str, str, bytes]:
    if not isinstance(payload, Mapping):
        raise LocalDocumentIntakeStop("upload payload must be a JSON object")
    expected = {"action", "document_type", "filename", "content_base64"}
    if set(payload) != expected:
        raise LocalDocumentIntakeStop("upload payload contains unexpected fields")
    if payload.get("action") != "use_as_base_document":
        raise LocalDocumentIntakeStop("action must be use_as_base_document")

    document_type = _required_text(payload, "document_type")
    if document_type not in DOCUMENT_TYPES:
        raise LocalDocumentIntakeStop("unsupported application document type")

    filename = Path(_required_text(payload, "filename")).name
    if Path(filename).suffix.casefold() != ".pdf":
        raise LocalDocumentIntakeStop("only PDF base documents are supported")

    encoded = _required_text(payload, "content_base64")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise LocalDocumentIntakeStop("content_base64 is invalid") from exc
    if not content:
        raise LocalDocumentIntakeStop("uploaded PDF is empty")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise LocalDocumentIntakeStop("uploaded PDF exceeds the 8 MiB local limit")
    if not content.startswith(b"%PDF"):
        raise LocalDocumentIntakeStop("uploaded content is not a PDF")
    return document_type, filename, content


def ingest_local_base_document(payload: object) -> dict[str, object]:
    document_type, filename, content = parse_upload_payload(payload)
    root = private_document_root()
    upload_root = root / "uploads"
    upload_root.mkdir(parents=True, exist_ok=True)

    content_sha256 = sha256(content).hexdigest()
    safe_name = _FILENAME_RE.sub("_", filename).strip("._") or "document.pdf"
    stored_path = upload_root / f"{document_type}-{content_sha256[:12]}-{safe_name}"
    temporary_path = stored_path.with_suffix(stored_path.suffix + ".uploading")

    try:
        temporary_path.write_bytes(content)
        extracted_text = extract_private_application_source_text(temporary_path)
        temporary_path.replace(stored_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    document = build_document(
        document_type=document_type,
        path=stored_path,
        private_root=root,
        source_label=(
            "Current approved base CV"
            if document_type == "base_cv"
            else "Current approved base application letter"
        ),
    )

    conn = connect()
    try:
        ensure_schema(conn)
        current = load_current_approved(conn)
        plan = build_plan(documents=(document,), current=current)
        changed, unchanged = apply_documents(
            conn,
            documents=(document,),
            approved_by="local_operator",
        )
    finally:
        conn.close()

    return {
        "status": "approved",
        "document_type": document_type,
        "filename": filename,
        "source_reference": document.source_reference,
        "content_sha256": document.content_sha256,
        "byte_count": document.byte_count,
        "extracted_text_char_count": len(extracted_text),
        "would_change": bool(plan["would_change_count"]),
        "inserted_or_updated": changed,
        "unchanged": unchanged,
        "analysis": {
            "mode": "local_deterministic_pdf_text_extraction",
            "extractable_text": bool(extracted_text.strip()),
            "provider_or_llm_requests": 0,
        },
        "boundaries": {
            "document_content_persisted_to_database": False,
            "private_file_stored_locally": True,
            "database_writes": bool(changed),
            "provider_or_llm_requests": 0,
            "network_requests": 0,
            "application_submission_actions": False,
        },
    }


__all__ = [
    "LocalDocumentIntakeStop",
    "MAX_DOCUMENT_BYTES",
    "ingest_local_base_document",
    "parse_upload_payload",
    "private_document_root",
]
