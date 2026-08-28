"""Bounded Workday acquisition composition for strict employer-origin proof.

The path is deliberately small and evidence-derived:

    authorized employer/Workday root
      -> exact Workday CXS inventory POST
      -> one same-board public externalPath
      -> exact same-host CXS detail GET
      -> unchanged genuine_job_detail_proof

No Workday tenant, site, job identity, or target host is guessed.  A delegated
Workday board exists only when the already-authorized employer page exposes the
strict board/control evidence accepted by ``employer_origin_workday_navigation``.
The public SPA detail URL remains the canonical returned job URL; the CXS detail
endpoint is only a proof/content carrier.

Network I/O is injected through ``request_executor`` so callers retain metering
and transport authority.  This module performs no persistence, provider, LLM,
Tavily, connector-registration, lifecycle, or product actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    allowed_host,
    canonical_url,
    genuine_job_detail_proof,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_workday_detail import (
    workday_cxs_detail_page,
    workday_cxs_detail_url,
)
from src.connectors.employer_origin_workday_navigation import (
    WorkdayBoardRoute,
    explicit_workday_board_routes_from_employer_page,
    workday_board_route,
    workday_detail_urls_from_inventory,
    workday_inventory_json_fields,
)


MAX_BODY_BYTES = 5_000_000


@dataclass(frozen=True)
class WorkdayAcquisitionRequest:
    url: str
    method: str = "GET"
    json_fields: tuple[tuple[str, object], ...] = ()


RequestExecutor = Callable[[WorkdayAcquisitionRequest], tuple[str, str, int]]


def _bounded_body(value: object) -> str:
    text = str(value)
    if len(text.encode("utf-8", errors="replace")) > MAX_BODY_BYTES:
        raise RuntimeError("Workday acquisition response body cap exceeded")
    return text


def _route_from_root(
    *,
    root_url: str,
    root_html: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> WorkdayBoardRoute | None:
    """Resolve exactly one Workday route from already-authorized root evidence."""

    direct = workday_board_route(root_url, allowed_hosts=allowed_hosts)
    if direct is not None:
        return direct

    routes = explicit_workday_board_routes_from_employer_page(
        page_url=root_url,
        html=root_html,
        allowed_hosts=allowed_hosts,
        limit=2,
    )
    return routes[0] if len(routes) == 1 else None


def acquire_workday_job_page(
    *,
    listing_url: str,
    allowed_hosts: tuple[str, ...],
    request_executor: RequestExecutor,
) -> tuple[AcquiredJobPage | None, str]:
    """Attempt one strict Workday job proof with at most three injected requests.

    A successful delegated path consumes exactly three requests: root GET,
    inventory POST, CXS detail GET.  The Workday board and public SPA detail are
    not fetched merely to reconfirm routes that were already derived from strict
    root/inventory evidence.
    """

    if not allowed_hosts:
        raise ValueError("allowed_hosts must not be empty")

    root_request = WorkdayAcquisitionRequest(listing_url)
    root_body_raw, root_final_raw, root_status_raw = request_executor(root_request)
    root_body = _bounded_body(root_body_raw)
    root_final = str(root_final_raw)
    root_status = int(root_status_raw)
    if root_status >= 400:
        return None, root_final
    if not allowed_host(root_final, allowed_hosts):
        raise RuntimeError("Workday acquisition root source binding mismatch")

    root = parse_page(
        requested_url=listing_url,
        html=root_body,
        final_url=root_final,
        status_code=root_status,
    )
    route = _route_from_root(
        root_url=root.final_url,
        root_html=root.html,
        allowed_hosts=allowed_hosts,
    )
    if route is None:
        return None, root.final_url

    inventory_request = WorkdayAcquisitionRequest(
        route.inventory_url,
        "POST",
        workday_inventory_json_fields(),
    )
    inventory_body_raw, inventory_final_raw, inventory_status_raw = request_executor(
        inventory_request
    )
    inventory_body = _bounded_body(inventory_body_raw)
    inventory_final = str(inventory_final_raw)
    inventory_status = int(inventory_status_raw)
    if (
        inventory_status >= 400
        or canonical_url(inventory_final) != route.inventory_url
        or url_host(inventory_final) != route.host
    ):
        return None, root.final_url

    public_details = workday_detail_urls_from_inventory(
        inventory_url=route.inventory_url,
        body=inventory_body,
        public_board_url=route.public_board_url,
        allowed_hosts={route.host},
        limit=1,
    )
    if len(public_details) != 1:
        return None, root.final_url
    public_detail_url = public_details[0]

    cxs_detail_url = workday_cxs_detail_url(
        public_detail_url,
        public_board_url=route.public_board_url,
        allowed_hosts={route.host},
    )
    if cxs_detail_url is None:
        return None, root.final_url

    detail_request = WorkdayAcquisitionRequest(cxs_detail_url)
    detail_body_raw, detail_final_raw, detail_status_raw = request_executor(detail_request)
    detail_body = _bounded_body(detail_body_raw)
    detail_final = str(detail_final_raw)
    detail_status = int(detail_status_raw)

    proof_page = workday_cxs_detail_page(
        public_detail_url=public_detail_url,
        public_board_url=route.public_board_url,
        response_url=detail_final,
        status_code=detail_status,
        body=detail_body,
        allowed_hosts={route.host},
    )
    if proof_page is None:
        return None, root.final_url

    proof = genuine_job_detail_proof(
        proof_page,
        allowed_hosts={route.host},
        known_detail=True,
    )
    if proof is None:
        return None, root.final_url

    return (
        AcquiredJobPage(
            requested_url=public_detail_url,
            final_url=public_detail_url,
            status_code=detail_status,
            title=proof_page.title,
            html_bytes=len(proof_page.html.encode("utf-8", errors="replace")),
            proof_kind=proof,
            discovery_source="workday_cxs_inventory_detail",
            anchor_text="",
        ),
        root.final_url,
    )


__all__ = [
    "WorkdayAcquisitionRequest",
    "acquire_workday_job_page",
]
