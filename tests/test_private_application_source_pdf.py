from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from scripts.import_private_application_source_documents import build_document
from src.search_intelligence.product_v1_application_workspace import (
    ApplicationWorkspaceStop,
    local_document_loader,
)


def _write_text_pdf(path: Path, text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = (
        "BT\n/F1 12 Tf\n72 720 Td\n(" + escaped + ") Tj\nET\n"
    ).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode("ascii"))
        payload.extend(obj)
        payload.extend(b"\nendobj\n")

    xref_offset = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    result = bytes(payload)
    path.write_bytes(result)
    return result


def test_importer_accepts_text_bearing_pdf_without_persisting_content(tmp_path: Path) -> None:
    root = tmp_path / "private_application_sources"
    root.mkdir()
    source = root / "base_cv.pdf"
    payload = _write_text_pdf(source, "Current PDF CV")

    document = build_document(
        document_type="base_cv",
        path=source,
        private_root=root,
        source_label="Current approved base CV",
    )

    assert document.source_reference == "local://base_cv.pdf"
    assert document.content_sha256 == sha256(payload).hexdigest()
    assert document.byte_count == len(payload)
    assert not hasattr(document, "content")


def test_workspace_loader_extracts_text_from_local_pdf(tmp_path: Path) -> None:
    source = tmp_path / "base_application_letter.pdf"
    _write_text_pdf(source, "Current PDF application letter")

    content = local_document_loader(private_root=tmp_path)(
        "local://base_application_letter.pdf"
    )

    assert "Current PDF application letter" in content


def test_workspace_loader_rejects_pdf_without_extractable_text(tmp_path: Path) -> None:
    source = tmp_path / "base_cv.pdf"
    _write_text_pdf(source, "")

    with pytest.raises(ApplicationWorkspaceStop, match="no extractable text"):
        local_document_loader(private_root=tmp_path)("local://base_cv.pdf")
