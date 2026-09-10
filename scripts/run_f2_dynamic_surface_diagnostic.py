"""Read-only F2 diagnostic for JavaScript-backed Employer-Origin surfaces.

The diagnostic selects recent persisted-but-inactive Employer-Origin candidates,
fetches only their authorized root, a bounded number of exact-host script assets,
and a bounded set of exact-host route literals. It emits learning evidence only:
no database writes, activation, proof promotion, or job ingestion occur here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
import requests

from src.config import get_database_config
from src.search_intelligence.dynamic_surface_evidence import (
    exact_host,
    extract_dynamic_route_literals,
    extract_html_dynamic_surface_evidence,
    same_host,
)

SCHEMA = "job_application_pipeline.f2_dynamic_surface_diagnostic.v2"
USER_AGENT = "job-application-pipeline-f2-dynamic-surface/0.2 (+bounded read-only)"
MAX_BODY_BYTES = 5_000_000
MAX_SCRIPT_BODY_BYTES = 4_000_000
MAX_ROUTE_BODY_BYTES = 2_000_000
MAX_ROUTE_PROBES = 6
_STATIC_SUFFIXES = (
    ".css", ".gif", ".ico", ".jpeg", ".jpg", ".js", ".png", ".svg", ".webp",
    ".woff", ".woff2", ".pdf",
)

BOUNDARY = {
    "database_reads": True,
    "database_writes": False,
    "candidate_url_writes": False,
    "source_activation": False,
    "bronze_write": False,
    "silver_write": False,
    "product_write": False,
    "network_methods": ["GET"],
    "script_fetch_scope": "exact authorized root host only",
    "route_probe_scope": "exact authorized root host only",
    "script_literals_are_learning_evidence_only": True,
    "route_probe_results_are_learning_evidence_only": True,
}


def _load_candidates(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (company_key)
                    id, company_key, company_name, candidate_url, status, updated_at
                FROM employer_origin_source_candidates
                WHERE candidate_url IS NOT NULL
                  AND btrim(candidate_url) <> ''
                ORDER BY company_key, updated_at DESC NULLS LAST, id DESC
            )
            SELECT id, company_key, company_name, candidate_url, status, updated_at
            FROM latest c
            WHERE NOT EXISTS (
                SELECT 1
                FROM search_profiles sp
                WHERE sp.source_name = 'generic_origin:' || c.company_key
                  AND sp.is_active = TRUE
            )
            ORDER BY c.updated_at DESC NULLS LAST, c.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(row) for row in cur.fetchall()]


def _get_response(
    session: requests.Session,
    url: str,
    *,
    timeout: float,
    max_bytes: int,
) -> tuple[requests.Response, str]:
    response = session.get(url, timeout=timeout, allow_redirects=True)
    body = response.content or b""
    if len(body) > max_bytes:
        raise RuntimeError(f"response body cap exceeded: {len(body)} > {max_bytes}")
    text = body.decode(response.encoding or "utf-8", errors="replace")
    return response, text


def _get(session: requests.Session, url: str, *, timeout: float, max_bytes: int) -> tuple[str, str, int]:
    response, text = _get_response(session, url, timeout=timeout, max_bytes=max_bytes)
    return text, str(response.url), int(response.status_code)


def _literal_json(item) -> dict[str, object]:
    return {
        "raw": item.raw,
        "normalized_url": item.normalized_url,
        "host": item.host,
        "markers": list(item.markers),
    }


def _route_probe_priority(url: str) -> tuple[int, int, str]:
    parsed = urlparse(url)
    path_query = f"{parsed.path}?{parsed.query}".casefold()
    strong = sum(marker in path_query for marker in ("serverless", "/api", "jobs", "positions", "vacanc"))
    medium = sum(marker in path_query for marker in ("stellen", "career", "opening", "posting"))
    return (-strong, -medium, path_query)


def _select_route_probes(root_final: str, literals: list[Any]) -> list[str]:
    root_host = exact_host(root_final)
    unique: list[str] = []
    for item in literals:
        url = str(getattr(item, "normalized_url", "") or "")
        if not url or exact_host(url) != root_host or url == root_final:
            continue
        parsed = urlparse(url)
        path = parsed.path.casefold()
        if path.endswith(_STATIC_SUFFIXES) or ":" in path:
            continue
        if url not in unique:
            unique.append(url)
    return sorted(unique, key=_route_probe_priority)[:MAX_ROUTE_PROBES]


def _json_shape(text: str, content_type: str) -> dict[str, object] | None:
    if "json" not in content_type.casefold() and not text.lstrip().startswith(("{", "[")):
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return {"parse": "failed"}
    if isinstance(payload, dict):
        return {"type": "object", "keys": sorted(str(key) for key in payload)[:40]}
    if isinstance(payload, list):
        first_keys: list[str] = []
        if payload and isinstance(payload[0], dict):
            first_keys = sorted(str(key) for key in payload[0])[:40]
        return {"type": "array", "length": len(payload), "first_item_keys": first_keys}
    return {"type": type(payload).__name__}


def _probe_routes(
    session: requests.Session,
    *,
    root_final: str,
    literals: list[Any],
    timeout_seconds: float,
) -> list[dict[str, object]]:
    probes: list[dict[str, object]] = []
    for url in _select_route_probes(root_final, literals):
        row: dict[str, object] = {"url": url}
        try:
            response, text = _get_response(
                session,
                url,
                timeout=timeout_seconds,
                max_bytes=MAX_ROUTE_BODY_BYTES,
            )
            content_type = str(response.headers.get("content-type") or "")[:160]
            nested = extract_dynamic_route_literals(text=text, base_url=str(response.url), max_literals=24)
            row.update(
                {
                    "status": int(response.status_code),
                    "final_url": str(response.url),
                    "content_type": content_type,
                    "body_bytes": len(response.content or b""),
                    "json_shape": _json_shape(text, content_type),
                    "route_literals": [_literal_json(item) for item in nested],
                }
            )
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"[:500]
        probes.append(row)
    return probes


def diagnose_candidate(
    row: dict[str, Any],
    *,
    timeout_seconds: float,
    max_scripts: int,
) -> dict[str, object]:
    root_url = str(row["candidate_url"])
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json,application/javascript,text/javascript,*/*;q=0.7",
        }
    )
    result: dict[str, object] = {
        "candidate_id": int(row["id"]),
        "company_key": str(row["company_key"]),
        "company_name": str(row["company_name"]),
        "candidate_url": root_url,
        "root_host": exact_host(root_url),
        "root": None,
        "same_host_scripts": [],
        "cross_host_script_sources": [],
        "route_probes": [],
        "route_hosts": [],
        "route_marker_counts": {},
    }

    try:
        root_html, root_final, root_status = _get(
            session,
            root_url,
            timeout=timeout_seconds,
            max_bytes=MAX_BODY_BYTES,
        )
    except Exception as exc:
        result["root"] = {"error": f"{type(exc).__name__}: {exc}"[:500]}
        return result

    html_evidence = extract_html_dynamic_surface_evidence(html=root_html, base_url=root_final)
    html_literals = extract_dynamic_route_literals(text=root_html, base_url=root_final)
    result["root"] = {
        "status": root_status,
        "final_url": root_final,
        "body_bytes": len(root_html.encode("utf-8")),
        "script_source_count": len(html_evidence.script_sources),
        "url_attributes": list(html_evidence.url_attributes),
        "route_literals": [_literal_json(item) for item in html_literals],
    }

    same_host_scripts = [url for url in html_evidence.script_sources if same_host(url, root_final)]
    cross_host_scripts = [url for url in html_evidence.script_sources if not same_host(url, root_final)]
    result["cross_host_script_sources"] = cross_host_scripts[:12]

    script_rows: list[dict[str, object]] = []
    all_literals = list(html_literals)
    for script_url in same_host_scripts[: max(0, max_scripts)]:
        script_row: dict[str, object] = {"url": script_url}
        try:
            script_text, script_final, script_status = _get(
                session,
                script_url,
                timeout=timeout_seconds,
                max_bytes=MAX_SCRIPT_BODY_BYTES,
            )
            literals = extract_dynamic_route_literals(text=script_text, base_url=script_final)
            all_literals.extend(literals)
            script_row.update(
                {
                    "status": script_status,
                    "final_url": script_final,
                    "body_bytes": len(script_text.encode("utf-8")),
                    "route_literals": [_literal_json(item) for item in literals],
                }
            )
        except Exception as exc:
            script_row["error"] = f"{type(exc).__name__}: {exc}"[:500]
        script_rows.append(script_row)
    result["same_host_scripts"] = script_rows
    result["route_probes"] = _probe_routes(
        session,
        root_final=root_final,
        literals=all_literals,
        timeout_seconds=timeout_seconds,
    )

    hosts = sorted({item.host for item in all_literals if item.host})
    marker_counts: dict[str, int] = {}
    for item in all_literals:
        for marker in item.markers:
            marker_counts[marker] = marker_counts.get(marker, 0) + 1
    result["route_hosts"] = hosts
    result["route_marker_counts"] = dict(sorted(marker_counts.items()))
    return result


def run(args: argparse.Namespace) -> int:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        rows = _load_candidates(conn, limit=args.candidate_limit)

    results = [
        diagnose_candidate(
            row,
            timeout_seconds=args.timeout_seconds,
            max_scripts=args.max_scripts_per_candidate,
        )
        for row in rows
    ]
    host_counts: dict[str, int] = {}
    marker_candidate_counts: dict[str, int] = {}
    for item in results:
        for host in item.get("route_hosts", []):
            host_counts[str(host)] = host_counts.get(str(host), 0) + 1
        for marker in item.get("route_marker_counts", {}):
            marker_candidate_counts[str(marker)] = marker_candidate_counts.get(str(marker), 0) + 1

    recurring_route_hosts = {
        host: count for host, count in sorted(host_counts.items()) if count >= 2
    }
    recurring_markers = {
        marker: count
        for marker, count in sorted(marker_candidate_counts.items())
        if count >= 2
    }
    payload = {
        "schema": SCHEMA,
        "boundary": BOUNDARY,
        "candidate_count": len(results),
        "results": results,
        "recurring_route_hosts": recurring_route_hosts,
        "recurring_markers": recurring_markers,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"F2_DYNAMIC_CANDIDATES={len(results)}")
    for item in results:
        root = item.get("root") or {}
        status = root.get("status") if isinstance(root, dict) else None
        scripts = item.get("same_host_scripts") or []
        routes = sum(
            len(script.get("route_literals") or [])
            for script in scripts
            if isinstance(script, dict)
        )
        errors = sum(
            1 for script in scripts if isinstance(script, dict) and script.get("error")
        )
        probes = item.get("route_probes") or []
        if isinstance(root, dict):
            routes += len(root.get("route_literals") or [])
        print(
            f"F2_DYNAMIC_SOURCE={item['company_key']}|status={status}|"
            f"same_host_scripts={len(scripts)}|route_literals={routes}|"
            f"route_probes={len(probes)}|script_errors={errors}"
        )
    print("F2_DYNAMIC_RECURRING_HOSTS=" + json.dumps(recurring_route_hosts, sort_keys=True))
    print("F2_DYNAMIC_RECURRING_MARKERS=" + json.dumps(recurring_markers, sort_keys=True))
    print(f"F2_DYNAMIC_ARTIFACT={output}")
    print("F2_DYNAMIC_SURFACE_DIAGNOSTIC=PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded read-only F2 dynamic surface evidence diagnostic.")
    parser.add_argument("--candidate-limit", type=int, default=8)
    parser.add_argument("--max-scripts-per-candidate", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--output", default="/tmp/jap-f2-dynamic-surface.json")
    return parser


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
