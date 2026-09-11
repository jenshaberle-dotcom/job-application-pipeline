"""Bounded product acquisition for employer-authorized B-ITE surfaces.

This module composes the provider mechanics from :mod:`employer_origin_bite` with
JAP's existing generic Employer-Origin evidence model.  It derives every tenant
value from the live employer page and tenant asset, loads one finite current
inventory, performs target/control discrimination locally over that complete
inventory, and still requires the unchanged strict genuine-job proof for every
emitted detail.

No company-specific values or known vacancy URLs are accepted as inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import requests

from src.connectors.employer_origin_acquisition import (
    AcquiredJobPage,
    canonical_url,
    parse_page,
)
from src.connectors.employer_origin_acquisition_v4 import discover_navigation_candidates
from src.connectors.employer_origin_bite import (
    BITE_API_ENDPOINT,
    BITE_API_HOST,
    BITE_ASSET_HOST,
    BITE_JOBS_API_CLIENT,
    BiteBinding,
    BitePosting,
    BiteRuntimeConfig,
    bite_inventory_payload,
    bite_raw_detail_url,
    discover_bite_binding,
    filter_bite_postings,
    parse_bite_postings,
    parse_bite_runtime,
    prove_bite_raw_detail,
)

MAX_BODY_BYTES = 5_000_000
DEFAULT_REQUEST_CAP = 40
DEFAULT_LISTING_FOLLOWUP_CAP = 2
DEFAULT_JOB_CAP = 30


@dataclass(frozen=True)
class BiteRequest:
    url: str
    method: str = "GET"
    json_body: dict[str, object] | None = None
    headers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class BiteBoundInventory:
    origin_url: str
    employer_page_url: str
    binding: BiteBinding
    runtime: BiteRuntimeConfig
    postings: tuple[BitePosting, ...]
    request_count: int


@dataclass(frozen=True)
class BiteProvenJob:
    posting: BitePosting
    job: AcquiredJobPage
    raw_url: str
    raw_body: str


@dataclass(frozen=True)
class BiteQueryResult:
    status: str
    reason: str
    jobs: tuple[BiteProvenJob, ...]
    request_count: int
    inventory_count: int = 0


RequestExecutor = Callable[[BiteRequest], tuple[str, str, int]]


class BiteProductExecutor:
    """Small HTTP executor with one absolute request budget."""

    def __init__(self, *, max_requests: int = DEFAULT_REQUEST_CAP, timeout_seconds: float = 30.0) -> None:
        self.max_requests = max_requests
        self.timeout_seconds = timeout_seconds
        self.calls = 0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "job-application-pipeline-bite-product/1.0",
                "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
            }
        )

    def __call__(self, request: BiteRequest) -> tuple[str, str, int]:
        if self.calls >= self.max_requests:
            raise RuntimeError("B-ITE product absolute request cap exceeded")
        self.calls += 1
        method = request.method.upper()
        headers = dict(request.headers)
        if method == "GET" and request.json_body is None:
            response = self.session.get(
                request.url,
                timeout=self.timeout_seconds,
                allow_redirects=True,
                headers=headers or None,
            )
        elif method == "POST" and request.json_body is not None:
            response = self.session.post(
                request.url,
                json=request.json_body,
                timeout=self.timeout_seconds,
                allow_redirects=False,
                headers=headers or None,
            )
        else:
            raise RuntimeError(f"unsupported B-ITE product request: {method}")
        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("B-ITE product response body cap exceeded")
        return (
            body.decode(response.encoding or "utf-8", errors="replace"),
            str(response.url),
            int(response.status_code),
        )


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().strip(".")


def _valid_same_host_https(url: str, host: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme.casefold() == "https"
        and (parsed.hostname or "").casefold() == host
        and not parsed.username
        and not parsed.password
    )


def _fetch_employer_page(
    url: str,
    *,
    expected_host: str,
    execute: RequestExecutor,
) -> tuple[str, str] | None:
    body, final_url, status = execute(BiteRequest(url))
    if not 200 <= int(status) < 400 or not _valid_same_host_https(final_url, expected_host):
        return None
    return body, final_url


def discover_bite_inventory(
    *,
    origin_url: str,
    execute: RequestExecutor,
    listing_followup_cap: int = DEFAULT_LISTING_FOLLOWUP_CAP,
) -> BiteBoundInventory | None:
    """Resolve employer page -> tenant asset -> one complete B-ITE inventory."""

    origin_host = _host(origin_url)
    if not origin_host or not _valid_same_host_https(origin_url, origin_host):
        return None

    fetched = _fetch_employer_page(origin_url, expected_host=origin_host, execute=execute)
    if fetched is None:
        return None
    root_body, root_url = fetched
    root = parse_page(
        requested_url=origin_url,
        html=root_body,
        final_url=root_url,
        status_code=200,
    )

    employer_page_url = root.final_url
    employer_page_body = root.html
    binding = discover_bite_binding(page_url=employer_page_url, html=employer_page_body)

    if binding is None and listing_followup_cap > 0:
        candidates = [
            item
            for item in discover_navigation_candidates(
                root,
                allowed_hosts=(origin_host,),
            )
            if item.kind == "listing" and _valid_same_host_https(item.url, origin_host)
        ]
        seen: set[str] = set()
        for item in candidates:
            clean = canonical_url(item.url)
            if not clean or clean in seen:
                continue
            seen.add(clean)
            if len(seen) > listing_followup_cap:
                break
            fetched = _fetch_employer_page(item.url, expected_host=origin_host, execute=execute)
            if fetched is None:
                continue
            body, final_url = fetched
            candidate_binding = discover_bite_binding(page_url=final_url, html=body)
            if candidate_binding is None:
                continue
            if binding is not None and candidate_binding != binding:
                return None
            binding = candidate_binding
            employer_page_url = final_url
            employer_page_body = body
            break

    if binding is None:
        return None

    asset_body, asset_final, asset_status = execute(BiteRequest(binding.asset_url))
    if (
        int(asset_status) != 200
        or canonical_url(asset_final) != canonical_url(binding.asset_url)
        or not _valid_same_host_https(asset_final, BITE_ASSET_HOST)
    ):
        return None
    runtime = parse_bite_runtime(
        binding=binding,
        asset_url=asset_final,
        javascript=asset_body,
    )
    if runtime is None:
        return None

    payload = bite_inventory_payload(runtime=runtime, origin_url=employer_page_url)
    inventory_body, inventory_final, inventory_status = execute(
        BiteRequest(
            BITE_API_ENDPOINT,
            "POST",
            payload,
            (
                ("Accept", "application/json"),
                ("Content-Type", "application/json;charset=utf-8"),
                ("Bite-JobsApi-Client", BITE_JOBS_API_CLIENT),
            ),
        )
    )
    if (
        int(inventory_status) != 200
        or canonical_url(inventory_final) != canonical_url(BITE_API_ENDPOINT)
        or not _valid_same_host_https(inventory_final, BITE_API_HOST)
    ):
        return None
    postings = parse_bite_postings(inventory_body, page_num=runtime.page_num)
    if postings is None:
        return None

    calls = getattr(execute, "calls", 0)
    return BiteBoundInventory(
        origin_url=origin_url,
        employer_page_url=employer_page_url,
        binding=binding,
        runtime=runtime,
        postings=postings,
        request_count=int(calls) if isinstance(calls, int) else 0,
    )


def _selected_postings(
    inventory: BiteBoundInventory,
    target_terms: list[str],
    *,
    control_term: str,
    job_cap: int,
) -> tuple[tuple[BitePosting, str], ...] | None:
    if filter_bite_postings(inventory.postings, control_term):
        return None
    selected: list[tuple[BitePosting, str]] = []
    seen: set[str] = set()
    for term in target_terms:
        for posting in filter_bite_postings(inventory.postings, term):
            identity = posting.posting_id
            if identity in seen:
                continue
            seen.add(identity)
            selected.append((posting, term))
            if len(selected) >= job_cap:
                return tuple(selected)
    return tuple(selected)


def acquire_bite_query_proven_jobs(
    *,
    origin_url: str,
    target_terms: list[str],
    control_term: str,
    execute: RequestExecutor | None = None,
    job_cap: int = DEFAULT_JOB_CAP,
) -> BiteQueryResult:
    """Return strict jobs only from a complete employer-authorized B-ITE inventory."""

    if not target_terms:
        raise ValueError("target_terms must not be empty")
    if not control_term:
        raise ValueError("control_term must not be empty")
    if job_cap < 1:
        raise ValueError("job_cap must be positive")

    http = execute or BiteProductExecutor()
    try:
        inventory = discover_bite_inventory(origin_url=origin_url, execute=http)
    except Exception as exc:
        calls = getattr(http, "calls", 0)
        return BiteQueryResult(
            "failed",
            f"bite_inventory_error:{type(exc).__name__}:{exc}",
            (),
            int(calls) if isinstance(calls, int) else 0,
        )
    if inventory is None:
        calls = getattr(http, "calls", 0)
        return BiteQueryResult(
            "not_available",
            "no_strict_employer_backed_bite_inventory",
            (),
            int(calls) if isinstance(calls, int) else 0,
        )

    selected = _selected_postings(
        inventory,
        target_terms,
        control_term=control_term,
        job_cap=job_cap,
    )
    calls = getattr(http, "calls", inventory.request_count)
    if selected is None:
        return BiteQueryResult(
            "failed",
            "impossible_control_query_returned_jobs",
            (),
            int(calls) if isinstance(calls, int) else inventory.request_count,
            len(inventory.postings),
        )
    if not selected:
        return BiteQueryResult(
            "unconfirmed_zero",
            "finite_inventory_target_terms_returned_zero_jobs",
            (),
            int(calls) if isinstance(calls, int) else inventory.request_count,
            len(inventory.postings),
        )

    jobs: list[BiteProvenJob] = []
    try:
        for posting, _term in selected:
            raw_url = bite_raw_detail_url(posting.url)
            if raw_url is None:
                continue
            body, final_url, status = http(BiteRequest(raw_url))
            job = prove_bite_raw_detail(
                posting=posting,
                raw_url=raw_url,
                raw_body=body,
                response_url=final_url,
                status_code=int(status),
            )
            if job is None:
                continue
            jobs.append(
                BiteProvenJob(
                    posting=posting,
                    job=job,
                    raw_url=raw_url,
                    raw_body=body,
                )
            )
    except Exception as exc:
        calls = getattr(http, "calls", inventory.request_count)
        return BiteQueryResult(
            "failed",
            f"bite_detail_error:{type(exc).__name__}:{exc}",
            (),
            int(calls) if isinstance(calls, int) else inventory.request_count,
            len(inventory.postings),
        )

    calls = getattr(http, "calls", inventory.request_count)
    if not jobs:
        return BiteQueryResult(
            "failed",
            "target_inventory_matched_but_no_detail_passed_strict_proof",
            (),
            int(calls) if isinstance(calls, int) else inventory.request_count,
            len(inventory.postings),
        )
    return BiteQueryResult(
        "proven",
        "finite_authoritative_inventory_target_match_control_zero",
        tuple(jobs),
        int(calls) if isinstance(calls, int) else inventory.request_count,
        len(inventory.postings),
    )


def prove_one_bite_source(
    *,
    origin_url: str,
    execute: RequestExecutor | None = None,
) -> tuple[BiteProvenJob, BiteBoundInventory] | None:
    """Prove one current job for source validity without role/profile filtering."""

    http = execute or BiteProductExecutor(max_requests=8)
    try:
        inventory = discover_bite_inventory(origin_url=origin_url, execute=http)
        if inventory is None or not inventory.postings:
            return None
        for posting in inventory.postings[:3]:
            raw_url = bite_raw_detail_url(posting.url)
            if raw_url is None:
                continue
            body, final_url, status = http(BiteRequest(raw_url))
            job = prove_bite_raw_detail(
                posting=posting,
                raw_url=raw_url,
                raw_body=body,
                response_url=final_url,
                status_code=int(status),
            )
            if job is not None:
                return (
                    BiteProvenJob(posting, job, raw_url, body),
                    inventory,
                )
    except Exception:
        return None
    return None


__all__ = [
    "BiteBoundInventory",
    "BiteProductExecutor",
    "BiteProvenJob",
    "BiteQueryResult",
    "BiteRequest",
    "acquire_bite_query_proven_jobs",
    "discover_bite_inventory",
    "prove_one_bite_source",
]
