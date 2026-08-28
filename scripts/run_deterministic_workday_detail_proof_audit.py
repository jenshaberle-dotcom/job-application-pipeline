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
from src.connectors.employer_origin_workday_detail import (
    workday_cxs_detail_page,
    workday_cxs_detail_url,
)
from src.connectors.employer_origin_workday_navigation import (
    explicit_workday_board_routes_from_employer_page,
    workday_detail_urls_from_inventory,
    workday_inventory_json_fields,
)


SCHEMA = "job_application_pipeline.deterministic_workday_detail_proof_audit.v1"
MAX_BODY_BYTES = 5_000_000
ABSOLUTE_REQUEST_CAP = 5


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


def run(*, employer_url: str, timeout_seconds: float) -> dict[str, object]:
    parsed = urlparse(employer_url)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise ValueError("employer URL must be absolute HTTPS")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-workday-detail-proof-audit/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    calls: list[dict[str, object]] = []

    def record(method: str, requested: str, response: requests.Response) -> str:
        if len(calls) >= ABSOLUTE_REQUEST_CAP:
            raise RuntimeError("absolute Workday detail-proof request cap exceeded")
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

    source_response = session.get(employer_url, timeout=timeout_seconds, allow_redirects=True)
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
            "requests": calls,
            "boundary": _boundary(calls),
        }
    route = routes[0]

    board_response = session.get(route.public_board_url, timeout=timeout_seconds, allow_redirects=True)
    record("GET", route.public_board_url, board_response)
    if board_response.status_code >= 400 or url_host(str(board_response.url)) != route.host:
        return {
            "schema": SCHEMA,
            "decision": "not_proven",
            "reason": "derived Workday board is not reachable on the exact observed canonical host",
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
            "requests": calls,
            "boundary": _boundary(calls),
        }
    public_detail_url = detail_urls[0]

    public_response = session.get(public_detail_url, timeout=timeout_seconds, allow_redirects=True)
    public_html = record("GET", public_detail_url, public_response)
    if public_response.status_code >= 400 or url_host(str(public_response.url)) != route.host:
        return {
            "schema": SCHEMA,
            "decision": "detail_not_proven",
            "reason": "derived public Workday detail did not stay on the exact authorized canonical host",
            "public_detail": _url_shape(public_detail_url),
            "requests": calls,
            "boundary": _boundary(calls),
        }

    public_page = parse_page(
        requested_url=public_detail_url,
        html=public_html,
        final_url=str(public_response.url),
        status_code=int(public_response.status_code),
    )
    public_proof = genuine_job_detail_proof(
        public_page,
        allowed_hosts={route.host},
        known_detail=True,
    )
    if public_proof:
        return {
            "schema": SCHEMA,
            "decision": "strict_job_proven",
            "reason": "public Workday detail passes unchanged strict genuine-job proof",
            "proof_surface": "public_html",
            "proof_kind": public_proof,
            "public_detail": _url_shape(public_detail_url),
            "requests": calls,
            "boundary": _boundary(calls),
        }

    cxs_detail_url = workday_cxs_detail_url(
        public_detail_url,
        public_board_url=route.public_board_url,
        allowed_hosts={route.host},
    )
    if cxs_detail_url is None:
        return {
            "schema": SCHEMA,
            "decision": "detail_not_proven",
            "reason": "public detail failed strict proof and no exact CXS detail route was derivable",
            "proof_surface": "public_html",
            "proof_kind": None,
            "public_detail": _url_shape(public_detail_url),
            "requests": calls,
            "boundary": _boundary(calls),
        }

    cxs_response = session.get(cxs_detail_url, timeout=timeout_seconds, allow_redirects=False)
    cxs_body = record("GET", cxs_detail_url, cxs_response)
    cxs_page = workday_cxs_detail_page(
        public_detail_url=public_detail_url,
        public_board_url=route.public_board_url,
        response_url=str(cxs_response.url),
        status_code=int(cxs_response.status_code),
        body=cxs_body,
        allowed_hosts={route.host},
    )
    cxs_proof = (
        genuine_job_detail_proof(
            cxs_page,
            allowed_hosts={route.host},
            known_detail=True,
        )
        if cxs_page is not None
        else None
    )

    return {
        "schema": SCHEMA,
        "decision": "strict_job_proven" if cxs_proof else "detail_not_proven",
        "reason": (
            "same-host Workday CXS detail projection passes unchanged strict genuine-job proof"
            if cxs_proof
            else "public HTML and exact same-host CXS detail both failed unchanged strict genuine-job proof"
        ),
        "proof_surface": "workday_cxs_detail" if cxs_page is not None else "cxs_detail_invalid",
        "proof_kind": cxs_proof,
        "public_detail": _url_shape(public_detail_url),
        "cxs_detail": _url_shape(cxs_detail_url),
        "requests": calls,
        "boundary": _boundary(calls),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--employer-url", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    payload = run(employer_url=args.employer_url, timeout_seconds=args.timeout_seconds)
    output = Path(args.output)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("============================================")
    print("DETERMINISTIC WORKDAY DETAIL PROOF AUDIT")
    print("============================================")
    print(f"decision={payload['decision']}")
    print(f"reason={payload['reason']}")
    print(f"proof_surface={payload.get('proof_surface')}")
    print(f"proof_kind={payload.get('proof_kind')}")
    print("boundary=" + json.dumps(payload["boundary"], sort_keys=True))
    print(f"artifact={output}")
    print("WORKDAY_DETAIL_PROOF_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
