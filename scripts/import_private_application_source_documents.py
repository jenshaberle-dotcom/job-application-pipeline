from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


APPROVAL_TOKEN = "PRODUCT-V1-APPLICATION-SOURCE-IMPORT-001"
LOCK_KEY = "DEMO-001:private_application_source_documents"
DOCUMENT_TYPES = ("base_cv", "base_application_letter")


@dataclass(frozen=True)
class ApplicationSourceDocument:
    document_type: str
    source_label: str
    source_reference: str
    content_sha256: str
    byte_count: int


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _read_utf8_text(path: Path) -> tuple[str, bytes]:
    payload = path.read_bytes()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"application source is not UTF-8 text: {path}") from exc
    _require(bool(text.strip()), f"application source is empty: {path}")
    return text, payload


def build_document(
    *,
    document_type: str,
    path: Path,
    private_root: Path,
    source_label: str,
) -> ApplicationSourceDocument:
    _require(document_type in DOCUMENT_TYPES, f"unsupported document type: {document_type}")
    root = private_root.expanduser().resolve()
    resolved = path.expanduser().resolve()
    _require(resolved.is_file(), f"application source file does not exist: {resolved}")
    _require(root in {resolved, *resolved.parents}, "application source escaped private root")
    _text, payload = _read_utf8_text(resolved)
    relative = resolved.relative_to(root).as_posix()
    return ApplicationSourceDocument(
        document_type=document_type,
        source_label=source_label.strip(),
        source_reference=f"local://{relative}",
        content_sha256=sha256(payload).hexdigest(),
        byte_count=len(payload),
    )


def build_documents(
    *,
    private_root: Path,
    base_cv: Path,
    base_application_letter: Path,
) -> tuple[ApplicationSourceDocument, ...]:
    return (
        build_document(
            document_type="base_cv",
            path=base_cv,
            private_root=private_root,
            source_label="Current approved base CV",
        ),
        build_document(
            document_type="base_application_letter",
            path=base_application_letter,
            private_root=private_root,
            source_label="Current approved base application letter",
        ),
    )


def ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.application_source_documents') AS relation")
        row = cur.fetchone()
    _require(row is not None and row["relation"] is not None, "application_source_documents is missing")


def load_current_approved(conn: psycopg.Connection[Any]) -> dict[str, Mapping[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                document_type,
                source_label,
                source_reference,
                content_sha256,
                status,
                approved_by,
                approved_at
            FROM application_source_documents
            WHERE document_type IN ('base_cv', 'base_application_letter')
              AND status = 'approved'
            ORDER BY document_type, id DESC
            """
        )
        rows = tuple(cur.fetchall())
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        document_type = str(row["document_type"])
        _require(document_type not in result, f"multiple approved {document_type} rows exist")
        result[document_type] = row
    return result


def build_plan(
    *,
    documents: tuple[ApplicationSourceDocument, ...],
    current: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    for document in documents:
        previous = current.get(document.document_type)
        previous_hash = None if previous is None else str(previous["content_sha256"])
        items.append(
            {
                **asdict(document),
                "existing_approved_sha256": previous_hash,
                "would_change": previous_hash != document.content_sha256,
            }
        )
    return {
        "schema": "job_application_pipeline.private_application_source_import.v1",
        "mode": "plan",
        "documents": items,
        "would_change_count": sum(1 for item in items if item["would_change"]),
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "document_content_persisted_to_database": False,
            "network_requests": 0,
            "provider_or_llm_requests": 0,
            "application_or_submission_actions": False,
        },
    }


def apply_documents(
    conn: psycopg.Connection[Any],
    *,
    documents: tuple[ApplicationSourceDocument, ...],
    approved_by: str,
) -> tuple[int, int]:
    inserted_or_updated = 0
    unchanged = 0
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (LOCK_KEY,))
        for document in documents:
            cur.execute(
                """
                SELECT id, content_sha256
                FROM application_source_documents
                WHERE document_type = %s
                  AND status = 'approved'
                ORDER BY id DESC
                """,
                (document.document_type,),
            )
            approved_rows = tuple(cur.fetchall())
            _require(
                len(approved_rows) <= 1,
                f"multiple approved {document.document_type} rows exist",
            )
            if approved_rows and str(approved_rows[0]["content_sha256"]) == document.content_sha256:
                unchanged += 1
                continue

            cur.execute(
                """
                UPDATE application_source_documents
                SET status = 'superseded', updated_at = now()
                WHERE document_type = %s
                  AND status = 'approved'
                """,
                (document.document_type,),
            )
            cur.execute(
                """
                INSERT INTO application_source_documents (
                    document_type,
                    source_label,
                    source_reference,
                    content_sha256,
                    status,
                    approved_by,
                    approved_at
                )
                VALUES (%s, %s, %s, %s, 'approved', %s, now())
                ON CONFLICT (document_type, content_sha256)
                DO UPDATE SET
                    source_label = EXCLUDED.source_label,
                    source_reference = EXCLUDED.source_reference,
                    status = 'approved',
                    approved_by = EXCLUDED.approved_by,
                    approved_at = EXCLUDED.approved_at,
                    updated_at = now()
                """,
                (
                    document.document_type,
                    document.source_label,
                    document.source_reference,
                    document.content_sha256,
                    approved_by,
                ),
            )
            inserted_or_updated += 1
    conn.commit()
    return inserted_or_updated, unchanged


def write_report(report: Mapping[str, object], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = output_dir / f"private_application_source_import_{stamp}.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or approve local-private base CV and application-letter sources."
    )
    parser.add_argument(
        "--private-root",
        type=Path,
        default=Path("private_application_sources"),
    )
    parser.add_argument("--base-cv", type=Path, required=True)
    parser.add_argument("--base-application-letter", type=Path, required=True)
    parser.add_argument("--approved-by", default="jens")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--approval-token")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".runtime/demo"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    approved_by = args.approved_by.strip()
    if not approved_by:
        raise SystemExit("approved_by must not be blank")
    if args.apply and args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("invalid application source approval token")

    documents = build_documents(
        private_root=args.private_root,
        base_cv=args.base_cv,
        base_application_letter=args.base_application_letter,
    )

    conn = connect()
    try:
        ensure_schema(conn)
        current = load_current_approved(conn)
        plan = build_plan(documents=documents, current=current)
        inserted_or_updated = 0
        unchanged = 0
        if args.apply:
            inserted_or_updated, unchanged = apply_documents(
                conn,
                documents=documents,
                approved_by=approved_by,
            )
        else:
            conn.rollback()
    finally:
        conn.close()

    report = {
        **plan,
        "mode": "apply" if args.apply else "plan",
        "inserted_or_updated": inserted_or_updated,
        "unchanged": unchanged,
        "boundaries": {
            **dict(plan["boundaries"]),
            "database_writes": bool(args.apply and inserted_or_updated),
        },
    }
    report_path = write_report(report, args.output_dir)

    print("============================================")
    print("PRIVATE APPLICATION SOURCE DOCUMENTS")
    print("============================================")
    print(f"MODE={report['mode']}")
    for item in report["documents"]:
        print(
            "DOCUMENT="
            f"{item['document_type']}|sha256={item['content_sha256']}|"
            f"bytes={item['byte_count']}|would_change={str(item['would_change']).lower()}|"
            f"reference={item['source_reference']}"
        )
    print(f"WOULD_CHANGE={report['would_change_count']}")
    print(f"INSERTED_OR_UPDATED={inserted_or_updated}")
    print(f"UNCHANGED={unchanged}")
    print("DOCUMENT_CONTENT_PERSISTED_TO_DATABASE=false")
    print("PROVIDER_REQUESTS=0")
    print(f"artifact={report_path.resolve()}")
    print("PRIVATE_APPLICATION_SOURCE_IMPORT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
