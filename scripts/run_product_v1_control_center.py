"""Serve the read-only Product V1 API and built React Control Center.

This server exposes product state only. It has no POST routes, provider calls,
source activation, candidate mutation, application submission or scheduler writes.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from scripts.run_employer_origin_candidate_queue_agent import DatabaseConfig
from src.search_intelligence.product_v1_service import build_product_v1_payload


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND_DIST = ROOT / "frontend" / "control-center" / "dist"


def _relation_exists(conn: psycopg.Connection[object], relation_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s) IS NOT NULL AS present", (f"public.{relation_name}",))
        row = cur.fetchone()
    return bool(row and row["present"])


def _fetch_all(conn: psycopg.Connection[object], query: str) -> list[dict[str, object]]:
    with conn.cursor() as cur:
        cur.execute(query)
        return [dict(row) for row in cur.fetchall()]


def _fetch_one(conn: psycopg.Connection[object], query: str) -> dict[str, object] | None:
    with conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()
    return dict(row) if row else None


def load_product_v1_payload() -> dict[str, object]:
    with psycopg.connect(DatabaseConfig.from_environment().dsn(), row_factory=dict_row) as conn:
        required_relations = {
            "search_term_cycle_state",
            "product_v1_ranking_policy",
            "gold_product_v1_job_readiness",
            "gold_product_v1_top_jobs",
            "gold_product_v1_application_readiness",
            "application_source_documents",
        }
        migration_ready = all(_relation_exists(conn, relation) for relation in required_relations)
        if not migration_ready:
            return build_product_v1_payload(
                wave_states=[],
                job_readiness=[],
                top_jobs=[],
                ranking_policy=None,
                application_readiness=[],
                application_sources=[],
                migration_ready=False,
            )

        wave_states = _fetch_all(
            conn,
            """
            SELECT
                source_name,
                search_profile_name,
                search_term,
                current_interval_days,
                next_due_at,
                last_quality_score,
                last_new_company_count,
                last_known_cooldown_hit_count,
                is_not_exclusion_enabled,
                current_exclusion_wave_index,
                last_wave_action,
                last_wave_completed_at
            FROM search_term_cycle_state
            WHERE source_name = 'stepstone'
            ORDER BY search_profile_name, search_term
            """,
        )
        job_readiness = _fetch_all(
            conn,
            """
            SELECT *
            FROM gold_product_v1_job_readiness
            ORDER BY
                CASE product_readiness_status
                    WHEN 'rankable' THEN 0
                    WHEN 'ranking_policy_required' THEN 1
                    WHEN 'origin_validation_required' THEN 2
                    ELSE 3
                END,
                profile_direction_score DESC NULLS LAST,
                publication_date DESC NULLS LAST,
                silver_job_id
            LIMIT 200
            """,
        )
        top_jobs = _fetch_all(
            conn,
            """
            SELECT *
            FROM gold_product_v1_top_jobs
            ORDER BY product_rank
            """,
        )
        ranking_policy = _fetch_one(
            conn,
            """
            SELECT *
            FROM product_v1_ranking_policy
            WHERE policy_key = 'default'
            """,
        )
        application_readiness = _fetch_all(
            conn,
            """
            SELECT *
            FROM gold_product_v1_application_readiness
            ORDER BY silver_job_id
            LIMIT 200
            """,
        )
        application_sources = _fetch_all(
            conn,
            """
            SELECT
                id,
                document_type,
                source_label,
                source_reference,
                content_sha256,
                status,
                approved_by,
                approved_at,
                created_at
            FROM application_source_documents
            ORDER BY document_type, created_at DESC
            """,
        )

    return build_product_v1_payload(
        wave_states=wave_states,
        job_readiness=job_readiness,
        top_jobs=top_jobs,
        ranking_policy=ranking_policy,
        application_readiness=application_readiness,
        application_sources=application_sources,
        migration_ready=True,
    )


class ProductV1Handler(BaseHTTPRequestHandler):
    server_version = "DeepOceanProductV1/0.1"

    @property
    def frontend_dist(self) -> Path:
        return self.server.frontend_dist  # type: ignore[attr-defined]

    def _send_bytes(
        self,
        body: bytes,
        *,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: object, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self._send_bytes(body, content_type="application/json; charset=utf-8", status=status)

    def _serve_frontend(self, requested_path: str) -> None:
        root = self.frontend_dist.resolve()
        if not (root / "index.html").is_file():
            body = (
                "<!doctype html><html><body><h1>React build required</h1>"
                "<p>Build frontend/control-center and restart this server. "
                "The read-only API is available at <code>/api/v1/product-v1</code>.</p>"
                "</body></html>"
            ).encode("utf-8")
            self._send_bytes(body, content_type="text/html; charset=utf-8", status=HTTPStatus.SERVICE_UNAVAILABLE)
            return

        relative = requested_path.lstrip("/")
        candidate = (root / relative).resolve() if relative else root / "index.html"
        if root not in candidate.parents and candidate != root:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            candidate = root / "index.html"
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        cache = "public, max-age=31536000, immutable" if "/assets/" in requested_path else "no-cache"
        self._send_bytes(candidate.read_bytes(), content_type=content_type, cache_control=cache)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_json(
                {
                    "status": "ok",
                    "mode": "read_only",
                    "provider_calls": False,
                    "mutations": False,
                }
            )
            return
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
        if parsed.path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        self._serve_frontend(parsed.path)

    def do_POST(self) -> None:  # noqa: N802 - explicit read-only boundary
        self._send_json(
            {
                "status": "blocked",
                "reason": "Product V1 API is read-only; operator actions require separate reviewed contracts.",
            },
            status=HTTPStatus.METHOD_NOT_ALLOWED,
        )

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("PRODUCT_V1_UI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PRODUCT_V1_UI_PORT", "8780")))
    parser.add_argument("--frontend-dist", type=Path, default=DEFAULT_FRONTEND_DIST)
    return parser


def run_server(args: argparse.Namespace) -> None:
    server = ThreadingHTTPServer((args.host, args.port), ProductV1Handler)
    server.frontend_dist = args.frontend_dist  # type: ignore[attr-defined]
    print(f"Deep Ocean Product V1 Control Center: http://{args.host}:{args.port}/")
    print("Boundary: read-only API, no provider call, no source activation, no application submission.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProduct V1 Control Center stopped by operator.")
    finally:
        server.server_close()


def main() -> None:
    run_server(build_parser().parse_args())


if __name__ == "__main__":
    main()
