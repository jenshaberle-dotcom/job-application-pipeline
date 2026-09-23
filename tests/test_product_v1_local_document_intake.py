from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import import_private_application_source_documents as importer
from scripts import product_v1_local_document_intake as intake


def _text_pdf(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = ("BT\n/F1 12 Tf\n72 720 Td\n(" + escaped + ") Tj\nET\n").encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream",
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
        (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n").encode("ascii")
    )
    return bytes(payload)


def _payload(document_type: str = "base_cv", filename: str = "cv.pdf") -> dict[str, object]:
    return {
        "action": "install_f6_authority_template",
        "document_type": document_type,
        "filename": filename,
        "content_base64": base64.b64encode(_text_pdf("Current application source")).decode("ascii"),
    }


def _accept_authority(document_type: str, content: bytes):
    return SimpleNamespace(
        template_id=f"f6-{document_type}",
        canonical_filename=(
            "Hornetsecurity_Jens_Haberle_Lebenslauf.pdf"
            if document_type == "base_cv"
            else "Hornetsecurity_Jens_Haberle_Anschreiben.pdf"
        ),
        sha256="a" * 64,
    )


def test_parse_upload_payload_accepts_bounded_exact_authority_pdf(monkeypatch) -> None:
    monkeypatch.setattr(intake, "validate_template_pdf", _accept_authority)
    document_type, filename, content = intake.parse_upload_payload(_payload())
    assert document_type == "base_cv"
    assert filename == "cv.pdf"
    assert content.startswith(b"%PDF")


def test_parse_upload_payload_rejects_non_pdf_and_unknown_type() -> None:
    bad = _payload(filename="cv.txt")
    with pytest.raises(intake.LocalDocumentIntakeStop, match="only PDF"):
        intake.parse_upload_payload(bad)

    bad = _payload(document_type="portfolio")
    with pytest.raises(intake.LocalDocumentIntakeStop, match="unsupported"):
        intake.parse_upload_payload(bad)


def test_ingest_keeps_only_current_authority_bytes_local_and_reuses_source_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "private"
    monkeypatch.setattr(intake, "validate_template_pdf", _accept_authority)
    monkeypatch.setattr(importer, "validate_template_pdf", _accept_authority)
    monkeypatch.setenv("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", str(root))

    class FakeConnection:
        def close(self) -> None:
            return None

    connection = FakeConnection()
    monkeypatch.setattr(intake, "connect", lambda: connection)
    monkeypatch.setattr(intake, "ensure_schema", lambda conn: None)
    monkeypatch.setattr(intake, "load_current_approved", lambda conn: {})

    applied: list[object] = []

    def fake_apply(conn, *, documents, approved_by):
        applied.extend(documents)
        assert approved_by == "local_operator"
        return 1, 0

    monkeypatch.setattr(intake, "apply_documents", fake_apply)

    result = intake.ingest_local_base_document(_payload())

    assert result["status"] == "approved"
    assert result["document_type"] == "base_cv"
    assert result["template_id"] == "f6-base_cv"
    assert result["canonical_filename"] == "Hornetsecurity_Jens_Haberle_Lebenslauf.pdf"
    assert result["template_authority"] == "f6_exact_hash_and_geometry"
    assert result["analysis"]["provider_or_llm_requests"] == 0
    assert result["analysis"]["extractable_text"] is True
    assert result["boundaries"]["document_content_persisted_to_database"] is False
    assert result["boundaries"]["private_file_stored_locally"] is True
    assert result["boundaries"]["legacy_template_bytes_retained"] is False
    assert len(applied) == 1
    stored = root / str(applied[0].source_reference).removeprefix("local://")
    assert stored.is_file()
    assert stored.read_bytes().startswith(b"%PDF")



def test_parse_upload_payload_rejects_visually_similar_but_non_authority_pdf(monkeypatch) -> None:
    def reject(*, document_type: str, content: bytes):
        raise intake.F6TemplateAuthorityStop(
            f"{document_type} is not the frozen F6 template"
        )

    monkeypatch.setattr(intake, "validate_template_pdf", reject)
    with pytest.raises(intake.LocalDocumentIntakeStop, match="not the frozen F6 template"):
        intake.parse_upload_payload(_payload())
