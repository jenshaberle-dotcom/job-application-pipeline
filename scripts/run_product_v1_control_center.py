"""Serve the canonical Product V1 Control Center.

The canonical launcher preserves the reviewed read models and deterministic
downstream evidence-preview GET endpoint. Exactly one narrowly allowlisted POST
action is exposed for the existing employer-origin final-approval gate. That
action requires explicit confirmation, accepts no legacy approval token, reuses
the existing A1 authorization + audit contract, and performs no registration,
activation, ingestion, provider, ranking or application action.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import ThreadingHTTPServer
import json
from urllib.parse import parse_qs, urlparse

if __package__:
    from scripts import product_v1_control_center_base as _base
    from scripts.product_v1_control_center_actions import (
        ControlCenterActionStop,
        FINAL_APPROVAL_ACTION_PATH,
        apply_final_approval_action,
        parse_final_approval_action_payload,
    )
    from scripts.product_v1_downstream_preview_runtime import (
        load_downstream_evidence_preview_payload,
    )
else:  # pragma: no cover - direct script execution
    import product_v1_control_center_base as _base
    from product_v1_control_center_actions import (
        ControlCenterActionStop,
        FINAL_APPROVAL_ACTION_PATH,
        apply_final_approval_action,
        parse_final_approval_action_payload,
    )
    from product_v1_downstream_preview_runtime import (
        load_downstream_evidence_preview_payload,
    )

from src.search_intelligence.product_v1_downstream_preview import DownstreamPreviewStop


build_parser = _base.build_parser
load_product_v1_payload = _base.load_product_v1_payload
load_source_connector_overview_payload = _base.load_source_connector_overview_payload
build_source_connector_overview = _base.build_source_connector_overview
rank_product_jobs = _base.rank_product_jobs
_HARD_FILTER_POLICY_RELATION = "product_v1_hard_filter_policy"
_MAX_ACTION_BODY_BYTES = 4096


class ProductV1Handler(_base.ProductV1Handler):
    """Canonical read-mostly handler with one reviewed final-approval action."""

    server_version = "DeepOceanProductV1/0.3"

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/product-v1":
            super().do_GET()
            return
        if parsed.path == "/api/v1/source-connectors":
            super().do_GET()
            return
        if parsed.path != "/api/v1/product-v1/evidence-preview":
            super().do_GET()
            return

        query = parse_qs(parsed.query, keep_blank_values=True)
        raw_ids = query.get("silver_job_id") or []
        if len(raw_ids) != 1:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": "exactly one silver_job_id query parameter is required",
                    "provider_requests": 0,
                    "database_writes": 0,
                    "product_authority": False,
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        try:
            silver_job_id = int(raw_ids[0])
        except (TypeError, ValueError):
            self._send_json(
                {
                    "status": "blocked",
                    "reason": "silver_job_id must be an integer",
                    "provider_requests": 0,
                    "database_writes": 0,
                    "product_authority": False,
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        try:
            self._send_json(load_downstream_evidence_preview_payload(silver_job_id))
        except DownstreamPreviewStop as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "database_writes": 0,
                    "product_authority": False,
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
                    "product_authority": False,
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _read_action_payload(self) -> object:
        content_type = str(self.headers.get("Content-Type") or "").split(";", 1)[0].strip().casefold()
        if content_type != "application/json":
            raise ControlCenterActionStop("action content type must be application/json")
        raw_length = str(self.headers.get("Content-Length") or "").strip()
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ControlCenterActionStop("valid Content-Length is required") from exc
        if content_length <= 0 or content_length > _MAX_ACTION_BODY_BYTES:
            raise ControlCenterActionStop("action body size is outside the allowed bound")
        raw_body = self.rfile.read(content_length)
        if len(raw_body) != content_length:
            raise ControlCenterActionStop("action body was truncated")
        try:
            return json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControlCenterActionStop("action body must be valid UTF-8 JSON") from exc

    def do_POST(self) -> None:  # noqa: N802 - exact reviewed action allowlist
        parsed = urlparse(self.path)
        if parsed.path != FINAL_APPROVAL_ACTION_PATH:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": "Product V1 POST route is not in the reviewed action allowlist.",
                },
                status=HTTPStatus.METHOD_NOT_ALLOWED,
            )
            return

        try:
            candidate_id, confirmation = parse_final_approval_action_payload(
                self._read_action_payload()
            )
            result = apply_final_approval_action(
                candidate_id=candidate_id,
                confirmation=confirmation,
            )
        except ControlCenterActionStop as exc:
            self._send_json(
                {
                    "status": "blocked",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "source_activation": False,
                    "product_authority": False,
                },
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        except (ValueError, RuntimeError) as exc:
            self._send_json(
                {
                    "status": "review_required",
                    "reason": str(exc),
                    "provider_requests": 0,
                    "source_activation": False,
                    "product_authority": False,
                },
                status=HTTPStatus.CONFLICT,
            )
            return

        status = (
            HTTPStatus.OK
            if result.get("status") in {"applied", "not_applicable"}
            else HTTPStatus.CONFLICT
        )
        self._send_json(result, status=status)


def run_server(args: argparse.Namespace) -> None:
    server = ThreadingHTTPServer((args.host, args.port), ProductV1Handler)
    server.frontend_dist = args.frontend_dist  # type: ignore[attr-defined]
    print(f"Deep Ocean Product V1 Control Center: http://{args.host}:{args.port}/")
    print(
        "Boundary: read models + deterministic evidence preview + reviewed final-approval gate action; "
        "no provider call, connector registration, source activation, ingestion, ranking mutation or application submission."
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProduct V1 Control Center stopped by operator.")
    finally:
        server.server_close()


def main() -> None:
    run_server(build_parser().parse_args())


def __getattr__(name: str):
    """Preserve existing module-level read helpers without duplicating the base."""

    return getattr(_base, name)


if __name__ == "__main__":
    main()
