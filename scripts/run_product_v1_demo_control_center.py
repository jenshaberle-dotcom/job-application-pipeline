"""Serve the Product V1 Control Center with the DEMO-001 Application Workspace.

The existing canonical Control Center remains the product truth source. This demo
runtime adds the bounded Application Workspace, local-private base-document intake,
and a read-only presentation enrichment for current job review. Presentation evidence
never changes ranking, Top-5 or application authority.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import ThreadingHTTPServer
import json
from typing import Mapping
from urllib.parse import parse_qs, urlparse

from scripts.product_v1_application_workspace_runtime import (
    application_workspace_payload,
    generate_application_draft_payload,
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
from src.search_intelligence.product_v1_application_workspace import (
    ApplicationWorkspaceStop,
)


PRODUCT_V1_PATH = "/api/v1/product-v1"
APPLICATION_WORKSPACE_PATH = "/api/v1/product-v1/application-workspace"
APPLICATION_DRAFT_PATH = "/api/v1/product-v1/application-draft"
APPLICATION_SOURCE_UPLOAD_PATH = "/api/v1/product-v1/application-source-upload"
_MAX_ACTION_BODY_BYTES = 4_096
_MAX_UPLOAD_BODY_BYTES = 12 * 1024 * 1024


class DemoActionStop(ValueError):
    pass


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


class ProductV1DemoHandler(ProductV1Handler):
    server_version = "DeepOceanProductV1/0.9-demo"

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

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == PRODUCT_V1_PATH:
            try:
                self._send_json(
                    enrich_product_payload_for_operator(load_product_v1_payload())
                )
            except Exception as exc:  # pragma: no cover - runtime diagnostics
                self._send_json(
                    {
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                    status=HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return
        if parsed.path != APPLICATION_WORKSPACE_PATH:
            super().do_GET()
            return
        try:
            payload = application_workspace_payload(self._workspace_job_id())
            self._send_json(payload)
        except (ApplicationWorkspaceStop, DemoActionStop) as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "database_writes": 0,
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

    def _read_demo_action_payload(self, *, max_bytes: int = _MAX_ACTION_BODY_BYTES) -> object:
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
        except (DemoActionStop, LocalDocumentIntakeStop, PrivateApplicationSourceTextError) as exc:
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

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == APPLICATION_SOURCE_UPLOAD_PATH:
            self._post_document_upload()
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
                if payload.get("status") == "draft_for_review"
                else HTTPStatus.CONFLICT
            )
            self._send_json(payload, status=status)
        except (ApplicationWorkspaceStop, DemoActionStop) as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "database_writes": 0,
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
    server = ThreadingHTTPServer((args.host, args.port), ProductV1DemoHandler)
    server.frontend_dist = args.frontend_dist  # type: ignore[attr-defined]
    print(f"Deep Ocean Product V1 DEMO-001: http://{args.host}:{args.port}/")
    print(
        "Boundary: real Product V1 truth + local-private document intake + bounded "
        "Application Workspace; no automatic submission or send."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProduct V1 DEMO-001 stopped by operator.")
    finally:
        server.server_close()


def main() -> None:
    run_server(build_parser().parse_args())


if __name__ == "__main__":
    main()
