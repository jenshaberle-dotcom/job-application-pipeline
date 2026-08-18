"""Serve the canonical read-only Product V1 Control Center.

The canonical launcher preserves the existing Product V1 and source-connector
read models and adds one read-only deterministic downstream evidence-preview
GET endpoint. POST remains explicitly blocked by the reviewed read-only contract.
"""

from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

if __package__:
    from scripts import product_v1_control_center_base as _base
    from scripts.product_v1_downstream_preview_runtime import (
        load_downstream_evidence_preview_payload,
    )
else:  # pragma: no cover - direct script execution
    import product_v1_control_center_base as _base
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


class ProductV1Handler(_base.ProductV1Handler):
    """Canonical read-only handler with deterministic downstream preview."""

    server_version = "DeepOceanProductV1/0.2"

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

    def do_POST(self) -> None:  # noqa: N802 - explicit canonical read-only boundary
        self._send_json(
            {
                "status": "blocked",
                "reason": "Product V1 API is read-only; operator actions require separate reviewed contracts.",
            },
            status=HTTPStatus.METHOD_NOT_ALLOWED,
        )


def run_server(args: argparse.Namespace) -> None:
    server = ThreadingHTTPServer((args.host, args.port), ProductV1Handler)
    server.frontend_dist = args.frontend_dist  # type: ignore[attr-defined]
    print(f"Deep Ocean Product V1 Control Center: http://{args.host}:{args.port}/")
    print(
        "Boundary: read-only API + deterministic evidence preview; no provider call, "
        "no DB mutation, no source activation, no application submission."
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
