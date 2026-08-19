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
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

import psycopg
from psycopg.rows import dict_row

if not __package__:  # direct ``python scripts/...`` execution
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

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
from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from src.search_intelligence.product_v1_downstream_preview import DownstreamPreviewStop


build_parser = _base.build_parser
load_source_connector_overview_payload = _base.load_source_connector_overview_payload
build_source_connector_overview = _base.build_source_connector_overview
rank_product_jobs = _base.rank_product_jobs
_HARD_FILTER_POLICY_RELATION = "product_v1_hard_filter_policy"
_MAX_ACTION_BODY_BYTES = 4096


def _merge_structured_job_locations(
    payload: dict[str, object],
    location_rows: list[dict[str, object]],
) -> dict[str, object]:
    """Attach explicit one-to-many Silver locations without rewriting legacy city truth."""

    by_job: dict[int, list[dict[str, object]]] = {}
    for row in location_rows:
        raw_id = row.get("silver_job_id")
        if raw_id is None:
            continue
        try:
            silver_job_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        by_job.setdefault(silver_job_id, []).append(
            {
                "city": str(row.get("city") or "").strip(),
                "country_code": str(row.get("country_code") or "").strip(),
                "is_primary": bool(row.get("is_primary")),
                "evidence_source": str(row.get("evidence_source") or "").strip(),
            }
        )

    result = dict(payload)
    for collection_name in ("job_readiness", "top_jobs"):
        raw_collection = result.get(collection_name)
        if not isinstance(raw_collection, list):
            continue
        enriched: list[object] = []
        for item in raw_collection:
            if not isinstance(item, dict):
                enriched.append(item)
                continue
            copied = dict(item)
            raw_id = copied.get("silver_job_id")
            try:
                silver_job_id = int(raw_id) if raw_id is not None else None
            except (TypeError, ValueError):
                silver_job_id = None
            copied["structured_locations"] = (
                list(by_job.get(silver_job_id, [])) if silver_job_id is not None else []
            )
            enriched.append(copied)
        result[collection_name] = enriched
    return result


def load_product_v1_payload() -> dict[str, object]:
    """Load canonical Product V1 truth plus existing structured location evidence."""

    payload = _base.load_product_v1_payload()
    raw_jobs = payload.get("job_readiness")
    if not isinstance(raw_jobs, list):
        return payload

    silver_job_ids = sorted(
        {
            int(item["silver_job_id"])
            for item in raw_jobs
            if isinstance(item, dict) and item.get("silver_job_id") is not None
        }
    )
    if not silver_job_ids:
        return payload

    with psycopg.connect(
        DatabaseConfig.from_environment().dsn(), row_factory=dict_row
    ) as conn:
        if not _base._relation_exists(conn, "silver_job_locations"):
            return payload
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    silver_job_id,
                    city,
                    country_code,
                    is_primary,
                    evidence_source
                FROM silver_job_locations
                WHERE silver_job_id = ANY(%s)
                ORDER BY silver_job_id, is_primary DESC, id
                """,
                (silver_job_ids,),
            )
            location_rows = [dict(row) for row in cur.fetchall()]
    return _merge_structured_job_locations(payload, location_rows)


class ProductV1Handler(_base.ProductV1Handler):
    """Canonical read-mostly handler with one reviewed final-approval action."""

    server_version = "DeepOceanProductV1/0.4"

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == "/api/v1/product-v1":
            try:
                self._send_json(load_product_v1_payload())
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
