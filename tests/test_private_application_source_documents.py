from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from scripts.import_private_application_source_documents import (
    build_document,
    build_documents,
    build_plan,
)


def test_build_documents_keeps_content_private_and_uses_local_references(tmp_path: Path) -> None:
    root = tmp_path / "private_application_sources"
    root.mkdir()
    cv = root / "base_cv.txt"
    letter = root / "base_application_letter.txt"
    cv.write_text("Current CV\n", encoding="utf-8")
    letter.write_text("Current application letter\n", encoding="utf-8")

    documents = build_documents(
        private_root=root,
        base_cv=cv,
        base_application_letter=letter,
    )

    assert [item.document_type for item in documents] == [
        "base_cv",
        "base_application_letter",
    ]
    assert documents[0].source_reference == "local://base_cv.txt"
    assert documents[1].source_reference == "local://base_application_letter.txt"
    assert documents[0].content_sha256 == sha256(b"Current CV\n").hexdigest()
    assert documents[1].content_sha256 == sha256(
        b"Current application letter\n"
    ).hexdigest()


def test_build_document_refuses_source_outside_private_root(tmp_path: Path) -> None:
    root = tmp_path / "private_application_sources"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")

    with pytest.raises(RuntimeError, match="escaped private root"):
        build_document(
            document_type="base_cv",
            path=outside,
            private_root=root,
            source_label="Current approved base CV",
        )


def test_build_document_requires_utf8_text(tmp_path: Path) -> None:
    root = tmp_path / "private_application_sources"
    root.mkdir()
    source = root / "base_cv.txt"
    source.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(RuntimeError, match="not UTF-8 text"):
        build_document(
            document_type="base_cv",
            path=source,
            private_root=root,
            source_label="Current approved base CV",
        )


def test_plan_reports_only_hash_change_and_no_content(tmp_path: Path) -> None:
    root = tmp_path / "private_application_sources"
    root.mkdir()
    cv = root / "base_cv.txt"
    letter = root / "base_application_letter.txt"
    cv.write_text("Current CV", encoding="utf-8")
    letter.write_text("Current letter", encoding="utf-8")
    documents = build_documents(
        private_root=root,
        base_cv=cv,
        base_application_letter=letter,
    )

    plan = build_plan(
        documents=documents,
        current={
            "base_cv": {"content_sha256": documents[0].content_sha256},
        },
    )

    assert plan["would_change_count"] == 1
    assert plan["documents"][0]["would_change"] is False
    assert plan["documents"][1]["would_change"] is True
    assert "content" not in plan["documents"][0]
    assert plan["boundaries"] == {
        "database_reads": True,
        "database_writes": False,
        "document_content_persisted_to_database": False,
        "network_requests": 0,
        "provider_or_llm_requests": 0,
        "application_or_submission_actions": False,
    }
