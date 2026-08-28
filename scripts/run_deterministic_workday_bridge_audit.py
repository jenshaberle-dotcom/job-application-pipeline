from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import requests

from src.connectors.employer_origin_acquisition import (
    genuine_job_detail_proof,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_workday_navigation import (
    explicit_workday_board_routes_from_employer_page,
    workday_detail_urls_from_inventory,
    workday_inventory_json_fields,
)


SCHEMA = "job_application_pipeline.deterministic_workday_bridge_audit.v1"
MAX_BODY_BYTES = 5_000_000
ABSOLUTE_REQUEST_CAP = 4


def _url_shape(value: str) -> dict[str, object]:
    parsed = urlparse(value)
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
        "query_keys": sorted({key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}),
    }


def _read_response(response: requests.Response) -> str:
    body = response.content
    if len(body) > MAX_BODY_BYTES:
        raise RuntimeError("response body cap exceeded")
    return body.decode(response.encoding or "utf-8", errors="replace")


def run(*, employer_url: str, timeout_seconds: float) -> dict[str, object]:
    parsed = urlparse(employer_url)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError("employer URL must be absolute HTTPS")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-workday-bridge-audit/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []

    def record(method: str, requested: str, response: requests.Response) -> str:
        if len(calls) >= ABSOLUTE_REQUEST_CAP:
            raise RuntimeError("absolute Workday bridge request cap exceeded")
        text = _read_response(response)
        calls.append(
            {
                "method": method,
                "requested": _url_shape(requested),
                "final": _url_shape(str(response.url)),
                "status": int(response.status_code),
                "body_bytes": len(response.content),
            }
        )
        return text

    source_response = session.get(
        employer_url,
        timeout=timeout_seconds,
        allow_redirects=True,
    )
    source_html = record("GET", employer_url, source_response)
    if source_response.status_code >= 400:
        raise RuntimeError(f"employer source returned HTTP {source_response.status_code}")

    source_final = str(source_response.url)
    source_host = url_host(source_final)
    if not source_host:
        raise RuntimeError("employer source has no final host")

    routes = explicit_workday_board_routes_from_employer_page(
        page_url=source_final,
        html=source_html,
        allowed_hosts={source_host},
        limit=3,
    )
    if len(routes) != 1:
        return {
            "schema": SCHEMA,
            "decision": "not_proven",
            "reason": "expected exactly one evidence-backed Workday board route",
            "route_count": len(routes),
            "routes": [
                {
                    "public_board": _url_shape(route.public_board_url),
                    "inventory": _url_shape(route.inventory_url),
                    "tenant": route.tenant,
                    "site": route.site,
                    "locale": route.locale,
                }
                for route in routes
            ],
            "requests": calls,
            "boundary": _boundary(calls),
        }

    route = routes[0]

    board_response = session.get(
        route.public_board_url,
        timeout=timeout_seconds,
        allow_redirects=True,
    )
    record("GET", route.public_board_url, board_response)
    if board_response.status_code >= 400 or url_host(str(board_response.url)) != route.host:
        return {
            "schema": SCHEMA,
            "decision": "not_proven",
            "reason": "derived Workday board is not reachable on the exact observed canonical host",
            "route": {
                "public_board": _url_shape(route.public_board_url),
                "inventory": _url_shape(route.inventory_url),
            },
            "requests": calls,
            "boundary": _boundary(calls),
        }

    inventory_response = session.post(
        route.inventory_url,
        json=dict(workday_inventory_json_fields()),
        timeout=timeout_seconds,
        allow_redirects=False,
        headers={"Content-Type": "application/json"},
    )
    inventory_body = record("POST", route.inventory_url, inventory_response)
    if inventory_response.status_code >= 400 or url_host(str(inventory_response.url)) != route.host:
        return {
            "schema": SCHEMA,
            "decision": "not_proven",
            "reason": "exact Workday CXS inventory request did not return an authorized success response",
            "route": {
                "public_board": _url_shape(route.public_board_url),
                "inventory": _url_shape(route.inventory_url),
            },
            "requests": calls,
            "boundary": _boundary(calls),
        }

    detail_urls = workday_detail_urls_from_inventory(
        inventory_url=route.inventory_url,
        body=inventory_body,
        public_board_url=route.public_board_url,
        allowed_hosts={route.host},
        limit=1,
    )
    if not detail_urls:
        return {
            "schema": SCHEMA,
            "decision": "inventory_reached_no_detail",
            "reason": "authorized Workday inventory returned no bounded valid public detail path",
            "route": {
                "public_board": _url_shape(route.public_board_url),
                "inventory": _url_shape(route.inventory_url),
            },
            "requests": calls,
            "boundary": _boundary(calls),
        }

    detail_url = detail_urls[0]
    detail_response = session.get(
        detail_url,
        timeout=timeout_seconds,
        allow_redirects=True,
    )
    detail_html = record("GET", detail_url, detail_response)
    if detail_response.status_code >= 400 or url_host(str(detail_response.url)) != route.host:
        return {
            "schema": SCHEMA,
            "decision": "detail_not_proven",
            "reason": "derived Workday detail did not stay on the exact authorized canonical host",
            "detail": _url_shape(detail_url),
            "requests": calls,
            "boundary": _boundary(calls),
        }

    page = parse_page(
        requested_url=detail_url,
        html=detail_html,
        final_url=str(detail_response.url),
        status_code=int(detail_response.status_code),
    )
    proof = genuine_job_detail_proof(
        page,
        allowed_hosts={route.host},
        known_detail=True,
    )

    return {
        "schema": SCHEMA,
        "decision": "strict_job_proven" if proof else "detail_not_proven",
        "reason": (
            "derived Workday detail passes unchanged strict genuine-job proof"
            if proof
            else "detail was reached but unchanged strict genuine-job proof did not pass"
        ),
        "route": {
            "public_board": _url_shape(route.public_board_url),
            "inventory": _url_shape(route.inventory_url),
            "tenant": route.tenant,
            "site": route.site,
            "locale": route.locale,
        },
        "detail": _url_shape(str(detail_response.url)),
        "proof_kind": proof,
        "requests": calls,
        "boundary": _boundary(calls),
    }


def _boundary(calls: list[dict[str, object]]) -> dict[str, object]:
    return {
        "http_requests": len(calls),
        "http_get_requests": sum(item.get("method") == "GET" for item in calls),
        "http_post_requests": sum(item.get("method") == "POST" for item in calls),
        "provider_requests": 0,
        "llm_requests": 0,
        "tavily_requests": 0,
        "database_writes": 0,
        "connector_materialization": 0,
        "query_values_persisted": 0,
        "absolute_request_cap": ABSOLUTE_REQUEST_CAP,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--employer-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    payload = run(
        employer_url=args.employer_url,
        timeout_seconds=args.timeout_seconds,
    )
    output = Path(args.output)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("============================================")
    print("DETERMINISTIC WORKDAY BRIDGE AUDIT")
    print("============================================")
    print(f"decision={payload['decision']}")
    print(f"reason={payload['reason']}")
    route = payload.get("route")
    if isinstance(route, dict):
        print("route=" + json.dumps(route, sort_keys=True))
    print(f"proof_kind={payload.get('proof_kind')}")
    print("boundary=" + json.dumps(payload["boundary"], sort_keys=True))
    print(f"artifact={output}")
    print("WORKDAY_BRIDGE_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
