"""Serve the Product V1 Control Center with the DEMO-001 Application Workspace.

The existing canonical Control Center remains the product truth source. This demo
runtime adds the bounded Application Workspace, local-private base-document intake,
F5 application tracking, and read-only presentation enrichments. Explicit F5
submission recording records only operator-confirmed truth that already happened;
it never submits an application externally.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, urlparse

from scripts.product_v1_application_workspace_runtime_quality import (
    application_workspace_payload,
    generate_application_draft_payload,
)
from scripts.product_v1_application_workspace_runtime import (
    ApplicationWorkspaceLifecycleStop,
    revalidate_application_target,
)
from scripts.product_v1_data_layers_runtime import load_data_layers_payload
from scripts.product_v1_f4c_source_health_runtime import (
    load_source_schedule_evidence,
    project_current_source_health,
)
from scripts.product_v1_f5_application_actions import (
    ApplicationActionError,
    parse_submission_record_request,
    record_operator_confirmed_submission,
)
from scripts.product_v1_f5_application_tracking_runtime import (
    load_application_tracking_payload,
)
from scripts.product_v1_runtime_mailbox_sync import (
    MailboxSyncScheduler,
    sync_mailbox,
)
from scripts.run_product_v1_f5_mailbox_silver_reconciliation_preflight import (
    build_tracking_job_linkage,
)
from scripts.product_v1_job_presentation_runtime import (
    enrich_product_payload_for_operator,
)
from scripts.product_v1_local_document_intake import (
    LocalDocumentIntakeStop,
    ingest_local_base_document,
)
from scripts.run_product_v1_control_center import (
    ProductV1Handler,
    build_parser,
    load_product_v1_payload,
)
from src.search_intelligence.private_application_source_text import (
    PrivateApplicationSourceTextError,
)
from src.search_intelligence.f6_template_review import (
    F6TemplateReviewStop,
    build_review_payload,
    combine_review_package,
    render_review_package,
)
from src.search_intelligence.product_v1_application_workspace import (
    ApplicationWorkspaceStop,
)


PRODUCT_V1_PATH = "/api/v1/product-v1"
DATA_LAYERS_PATH = "/api/v1/product-v1/data-layers"
APPLICATION_WORKSPACE_PATH = "/api/v1/product-v1/application-workspace"
APPLICATION_WORKSPACE_REVALIDATE_PATH = (
    "/api/v1/product-v1/application-workspace/revalidate"
)
APPLICATION_DRAFT_PATH = "/api/v1/product-v1/application-draft"
F6_TEMPLATE_REVIEW_PATH = "/api/v1/product-v1/f6-template-review"
F6_TEMPLATE_EXPORT_PATH = "/api/v1/product-v1/f6-template-export"
APPLICATION_SOURCE_UPLOAD_PATH = "/api/v1/product-v1/application-source-upload"
APPLICATION_SUBMISSION_RECORD_PATH = "/api/v1/product-v1/application-submission-record"
MAILBOX_SYNC_PATH = "/api/v1/product-v1/mailbox-sync"
_MAX_ACTION_BODY_BYTES = 4_096
_MAX_UPLOAD_BODY_BYTES = 12 * 1024 * 1024
_MAX_F6_EXPORT_BODY_BYTES = 256 * 1024
_DEFAULT_PRIVATE_DOCUMENT_ROOT = Path("private_application_sources")


class DemoActionStop(ValueError):
    pass


def configure_demo_private_document_root() -> Path:
    """Give upload and workspace loading one deterministic local-private root."""

    raw = os.environ.get("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", "").strip()
    root = Path(raw).expanduser().resolve() if raw else _DEFAULT_PRIVATE_DOCUMENT_ROOT.resolve()
    root.mkdir(parents=True, exist_ok=True)
    os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] = str(root)
    return root


def _json_transport_value(value: object) -> object:
    """Normalize PostgreSQL transport values without changing product semantics."""

    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_transport_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_transport_value(item) for item in value]
    return value


def _load_operator_product_payload() -> dict[str, object]:
    """Apply read-only operator enrichments and bounded F4C/F5 projections."""

    enriched = enrich_product_payload_for_operator(load_product_v1_payload())
    projected = project_current_source_health(
        enriched,
        schedule_evidence=load_source_schedule_evidence(),
    )
    tracking = load_application_tracking_payload()
    raw_jobs = projected.get("job_readiness")
    jobs = [row for row in raw_jobs if isinstance(row, dict)] if isinstance(raw_jobs, list) else []
    raw_applications = tracking.get("applications")
    applications = (
        [row for row in raw_applications if isinstance(row, dict)]
        if isinstance(raw_applications, list)
        else []
    )
    tracking["job_linkage"] = build_tracking_job_linkage(applications, jobs)
    projected["application_tracking"] = tracking
    return projected


def parse_application_draft_action_payload(payload: object) -> int:
    if not isinstance(payload, Mapping):
        raise DemoActionStop("action payload must be a JSON object")
    if set(payload) != {"action", "silver_job_id"}:
        raise DemoActionStop("action payload contains unexpected fields")
    if payload.get("action") != "generate_review_draft":
        raise DemoActionStop("action must be generate_review_draft")
    try:
        silver_job_id = int(payload.get("silver_job_id") or 0)
    except (TypeError, ValueError) as exc:
        raise DemoActionStop("silver_job_id must be an integer") from exc
    if silver_job_id <= 0:
        raise DemoActionStop("silver_job_id must be positive")
    return silver_job_id



def parse_application_revalidation_action_payload(payload: object) -> int:
    if not isinstance(payload, Mapping):
        raise DemoActionStop("action payload must be a JSON object")
    if set(payload) != {"action", "silver_job_id"}:
        raise DemoActionStop("action payload contains unexpected fields")
    if payload.get("action") != "revalidate_selected_vacancy":
        raise DemoActionStop("action must be revalidate_selected_vacancy")
    try:
        silver_job_id = int(payload.get("silver_job_id") or 0)
    except (TypeError, ValueError) as exc:
        raise DemoActionStop("silver_job_id must be an integer") from exc
    if silver_job_id <= 0:
        raise DemoActionStop("silver_job_id must be positive")
    return silver_job_id


def _source_manifest_sha256(payload: object) -> str:
    if not isinstance(payload, Mapping):
        raise DemoActionStop("current source manifest is unavailable")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _safe_pdf_filename_part(value: object, *, fallback: str) -> str:
    text = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_"
        for ch in str(value or "").strip()
    )
    compact = "_".join(part for part in text.split("_") if part)
    return (compact[:80] or fallback).strip("_")


def parse_f6_template_export_payload(
    payload: object,
) -> tuple[int, str, Mapping[str, object]]:
    if not isinstance(payload, Mapping):
        raise DemoActionStop("F6 export payload must be a JSON object")
    expected = {"action", "silver_job_id", "source_manifest_sha256", "documents"}
    if set(payload) != expected:
        raise DemoActionStop("F6 export payload contains unexpected fields")
    if payload.get("action") != "render_f6_review_package":
        raise DemoActionStop("F6 export action must be render_f6_review_package")
    try:
        silver_job_id = int(payload.get("silver_job_id") or 0)
    except (TypeError, ValueError) as exc:
        raise DemoActionStop("silver_job_id must be an integer") from exc
    if silver_job_id <= 0:
        raise DemoActionStop("silver_job_id must be positive")
    manifest_sha = str(payload.get("source_manifest_sha256") or "").strip().lower()
    if len(manifest_sha) != 64 or any(ch not in "0123456789abcdef" for ch in manifest_sha):
        raise DemoActionStop("source_manifest_sha256 must be a lowercase SHA-256")
    documents = payload.get("documents")
    if not isinstance(documents, Mapping):
        raise DemoActionStop("documents must be an object")
    return silver_job_id, manifest_sha, documents


class ProductV1DemoHandler(ProductV1Handler):
    server_version = "DeepOceanProductV1/0.12-demo"

    def _send_json(
        self, payload: object, *, status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        """Keep the live demo HTTP boundary strict but PostgreSQL-type safe."""

        super()._send_json(_json_transport_value(payload), status=status)

    def _workspace_job_id(self) -> int:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)
        raw_ids = query.get("silver_job_id") or []
        if len(raw_ids) != 1:
            raise DemoActionStop(
                "exactly one silver_job_id query parameter is required"
            )
        try:
            silver_job_id = int(raw_ids[0])
        except (TypeError, ValueError) as exc:
            raise DemoActionStop("silver_job_id must be an integer") from exc
        if silver_job_id <= 0:
            raise DemoActionStop("silver_job_id must be positive")
        return silver_job_id

    def _send_runtime_error(self, exc: Exception) -> None:
        self._send_json(
            {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == PRODUCT_V1_PATH:
            try:
                self._send_json(_load_operator_product_payload())
            except Exception as exc:  # pragma: no cover - runtime diagnostics
                self._send_runtime_error(exc)
            return
        if parsed.path == DATA_LAYERS_PATH:
            try:
                self._send_json(load_data_layers_payload(_load_operator_product_payload()))
            except Exception as exc:  # pragma: no cover - runtime diagnostics
                self._send_runtime_error(exc)
            return
        if parsed.path == F6_TEMPLATE_REVIEW_PATH:
            try:
                self._send_json(
                    build_review_payload(root=configure_demo_private_document_root())
                )
            except F6TemplateReviewStop as exc:
                self._send_json(
                    {
                        "status": "blocked",
                        "reason": str(exc),
                        "human_review_required": True,
                        "submission_actions": 0,
                        "send_actions": 0,
                    },
                    status=HTTPStatus.CONFLICT,
                )
            except Exception as exc:  # pragma: no cover - runtime diagnostics
                self._send_runtime_error(exc)
            return
        if parsed.path != APPLICATION_WORKSPACE_PATH:
            super().do_GET()
            return
        try:
            payload = application_workspace_payload(self._workspace_job_id())
            self._send_json(payload)
        except ApplicationWorkspaceLifecycleStop as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "database_writes": exc.database_writes,
                    "lifecycle_health_observation_writes": (
                        exc.lifecycle_health_observation_writes
                    ),
                    "application_writes": 0,
                    "submission_writes": 0,
                    "send_actions": 0,
                },
                status=HTTPStatus.CONFLICT,
            )
        except (ApplicationWorkspaceStop, DemoActionStop) as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "database_writes": 0,
                    "lifecycle_health_observation_writes": 0,
                    "application_writes": 0,
                    "submission_writes": 0,
                    "send_actions": 0,
                },
                status=HTTPStatus.CONFLICT,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            self._send_json(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "provider_requests": 0,
                    "database_writes": 0,
                    "application_writes": 0,
                    "submission_writes": 0,
                    "send_actions": 0,
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _read_demo_action_payload(
        self, *, max_bytes: int = _MAX_ACTION_BODY_BYTES
    ) -> object:
        content_type = (
            str(self.headers.get("Content-Type") or "")
            .split(";", 1)[0]
            .strip()
            .casefold()
        )
        if content_type != "application/json":
            raise DemoActionStop("action content type must be application/json")
        raw_length = str(self.headers.get("Content-Length") or "").strip()
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise DemoActionStop("valid Content-Length is required") from exc
        if content_length <= 0 or content_length > max_bytes:
            raise DemoActionStop("action body size is outside the allowed bound")
        raw_body = self.rfile.read(content_length)
        if len(raw_body) != content_length:
            raise DemoActionStop("action body was truncated")
        try:
            return json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DemoActionStop("action body must be valid UTF-8 JSON") from exc

    def _post_document_upload(self) -> None:
        try:
            payload = ingest_local_base_document(
                self._read_demo_action_payload(max_bytes=_MAX_UPLOAD_BODY_BYTES)
            )
            self._send_json(payload)
        except (
            DemoActionStop,
            LocalDocumentIntakeStop,
            PrivateApplicationSourceTextError,
        ) as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_or_llm_requests": 0,
                    "application_submission_actions": False,
                },
                status=HTTPStatus.BAD_REQUEST,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            self._send_json(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "provider_or_llm_requests": 0,
                    "application_submission_actions": False,
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _post_f6_template_export(self) -> None:
        """Render exact-template PDFs for explicit local operator review only."""

        try:
            silver_job_id, expected_manifest_sha, documents = (
                parse_f6_template_export_payload(
                    self._read_demo_action_payload(
                        max_bytes=_MAX_F6_EXPORT_BODY_BYTES
                    )
                )
            )
            workspace = application_workspace_payload(silver_job_id)
            if workspace.get("status") != "ready":
                raise DemoActionStop("current application workspace is not ready")
            workspace_payload = workspace.get("workspace")
            source_manifest = (
                workspace_payload.get("source_manifest")
                if isinstance(workspace_payload, Mapping)
                else None
            )
            current_manifest_sha = _source_manifest_sha256(source_manifest)
            if current_manifest_sha != expected_manifest_sha:
                raise DemoActionStop(
                    "draft source manifest is stale; regenerate review text before export"
                )

            rendered = render_review_package(
                root=configure_demo_private_document_root(),
                replacements_by_document=documents,
            )
            response_documents = []
            for document in rendered:
                canonical = Path(document.canonical_filename)
                download_filename = f"{canonical.stem}_JAP_review.pdf"
                response_documents.append(
                    {
                        "document_type": document.document_type,
                        "download_filename": download_filename,
                        "pdf_base64": base64.b64encode(document.pdf_bytes).decode("ascii"),
                        "render_evidence": document.render_evidence,
                    }
                )

            combined = combine_review_package(rendered)
            target = (
                workspace_payload.get("target")
                if isinstance(workspace_payload, Mapping)
                else None
            )
            employer = (
                target.get("company_name")
                if isinstance(target, Mapping)
                else None
            )
            package_filename = (
                "JAP_Bewerbung_"
                + _safe_pdf_filename_part(employer, fallback="Bewerbung")
                + ".pdf"
            )
            self._send_json(
                {
                    "schema": "job_application_pipeline.f6_template_export.v2",
                    "status": "rendered_for_review",
                    "campaign": "F6",
                    "slice": "C",
                    "silver_job_id": silver_job_id,
                    "source_manifest_sha256": current_manifest_sha,
                    "package": {
                        "download_filename": package_filename,
                        "pdf_base64": base64.b64encode(combined.pdf_bytes).decode("ascii"),
                        "sha256": combined.sha256,
                        "page_count": combined.page_count,
                        "component_order": list(combined.component_order),
                        "page_identity": list(combined.page_identity),
                        "visual_identity": all(
                            item.get("visual_identity") is True
                            for item in combined.page_identity
                        ),
                    },
                    "documents": response_documents,
                    "transport": "loopback_json_base64",
                    "database_writes": 0,
                    "provider_requests": 0,
                    "application_actions": 0,
                    "submission_actions": 0,
                    "send_actions": 0,
                    "human_review_required": True,
                    "draft_approval_authority": False,
                    "application_authority": False,
                    "submission_authority": False,
                    "send_authority": False,
                }
            )
        except (DemoActionStop, F6TemplateReviewStop) as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "database_writes": 0,
                    "provider_requests": 0,
                    "application_actions": 0,
                    "submission_actions": 0,
                    "send_actions": 0,
                    "human_review_required": True,
                },
                status=HTTPStatus.CONFLICT,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            self._send_runtime_error(exc)

    def _post_submission_record(self) -> None:
        """Record an operator-confirmed past submission; never submit externally."""

        try:
            raw = self._read_demo_action_payload()
            if not isinstance(raw, Mapping):
                raise ApplicationActionError("action_payload_must_be_object")
            request = parse_submission_record_request(raw)
            result = record_operator_confirmed_submission(request)
            self._send_json(
                {
                    **result,
                    "authority": "explicit_operator_confirmation",
                    "email_actions": 0,
                    "provider_requests": 0,
                    "external_submission_actions": 0,
                }
            )
        except (DemoActionStop, ApplicationActionError) as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "email_actions": 0,
                    "provider_requests": 0,
                    "external_submission_actions": 0,
                },
                status=HTTPStatus.CONFLICT,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            self._send_json(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "email_actions": 0,
                    "provider_requests": 0,
                    "external_submission_actions": 0,
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == MAILBOX_SYNC_PATH:
            result = sync_mailbox(reason="operator_refresh")
            status = HTTPStatus.OK if result.get("status") in {"pass", "already_running"} else HTTPStatus.SERVICE_UNAVAILABLE
            self._send_json(result, status=status)
            return
        if parsed.path == APPLICATION_SOURCE_UPLOAD_PATH:
            self._post_document_upload()
            return
        if parsed.path == F6_TEMPLATE_EXPORT_PATH:
            self._post_f6_template_export()
            return
        if parsed.path == APPLICATION_SUBMISSION_RECORD_PATH:
            self._post_submission_record()
            return
        if parsed.path == APPLICATION_WORKSPACE_REVALIDATE_PATH:
            try:
                silver_job_id = parse_application_revalidation_action_payload(
                    self._read_demo_action_payload()
                )
                result = revalidate_application_target(silver_job_id)
                self._send_json(
                    {
                        "status": result.status,
                        "outcome": result.outcome,
                        "reason": result.evidence_reason,
                        "silver_job_id": silver_job_id,
                        "vacancy_revalidation_http_gets": result.http_requests,
                        "database_writes": result.health_observation_writes,
                        "lifecycle_health_observation_writes": (
                            result.health_observation_writes
                        ),
                        "provider_requests": 0,
                        "application_writes": 0,
                        "submission_writes": 0,
                        "send_actions": 0,
                    }
                )
            except (ApplicationWorkspaceStop, DemoActionStop) as exc:
                self._send_json(
                    {
                        "status": "blocked",
                        "reason": str(exc),
                        "vacancy_revalidation_http_gets": 0,
                        "database_writes": 0,
                        "lifecycle_health_observation_writes": 0,
                        "provider_requests": 0,
                        "application_writes": 0,
                        "submission_writes": 0,
                        "send_actions": 0,
                    },
                    status=HTTPStatus.CONFLICT,
                )
            return
        if parsed.path != APPLICATION_DRAFT_PATH:
            super().do_POST()
            return
        try:
            silver_job_id = parse_application_draft_action_payload(
                self._read_demo_action_payload()
            )
            payload = generate_application_draft_payload(silver_job_id)
            status = (
                HTTPStatus.OK
                if payload.get("status") in {"draft_for_review", "draft_unavailable"}
                else HTTPStatus.CONFLICT
            )
            self._send_json(payload, status=status)
        except ApplicationWorkspaceLifecycleStop as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "database_writes": exc.database_writes,
                    "lifecycle_health_observation_writes": (
                        exc.lifecycle_health_observation_writes
                    ),
                    "application_writes": 0,
                    "submission_writes": 0,
                    "send_actions": 0,
                },
                status=HTTPStatus.CONFLICT,
            )
        except (ApplicationWorkspaceStop, DemoActionStop) as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "database_writes": 0,
                    "lifecycle_health_observation_writes": 0,
                    "application_writes": 0,
                    "submission_writes": 0,
                    "send_actions": 0,
                },
                status=HTTPStatus.CONFLICT,
            )
        except Exception as exc:  # pragma: no cover - runtime diagnostics
            self._send_json(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "database_writes": 0,
                    "application_writes": 0,
                    "submission_writes": 0,
                    "send_actions": 0,
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )


def run_server(args: argparse.Namespace) -> None:
    private_root = configure_demo_private_document_root()
    server = ThreadingHTTPServer((args.host, args.port), ProductV1DemoHandler)
    server.frontend_dist = args.frontend_dist  # type: ignore[attr-defined]
    mailbox_scheduler = MailboxSyncScheduler()
    mailbox_scheduler.start()
    print(f"Deep Ocean Product V1 DEMO-001: http://{args.host}:{args.port}/")
    print(f"Private application documents: {private_root}")
    print(
        "Boundary: real Product V1 truth + read-only Bronze/Silver/Gold observability + "
        "current source-health projection + local-private document intake + bounded "
        "Application Workspace + explicit operator-confirmed application tracking; "
        "no automatic submission or send."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProduct V1 DEMO-001 stopped by operator.")
    finally:
        mailbox_scheduler.stop()
        server.server_close()


def main() -> None:
    run_server(build_parser().parse_args())


if __name__ == "__main__":
    main()
