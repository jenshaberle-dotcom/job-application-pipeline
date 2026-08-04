"""Install execution safeguards around the staged origin-search runtime.

This contract is installed after the staged module is imported. It narrows raw
Tavily-domain follow-ups to domains related to the current query and isolates a
single transport failure without retrying the same query.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse

import requests

from scripts import run_origin_url_adaptive_repair as adaptive_runtime
from src.search_intelligence import adaptive_origin_search as adaptive_contracts
from src.search_intelligence.origin_search_runtime_contract import (
    is_followup_excluded_domain,
)
from src.search_intelligence.origin_source_discovery_agent import ascii_fold

_INSTALL_MARKER = "_origin_search_execution_contract_installed"
_ORIGINAL_SEARCH_ROWS = "_origin_search_original_search_rows"
_ORIGINAL_DOMAINS_FROM_ROWS = "_origin_search_original_domains_from_rows"
_ORIGINAL_LEDGER_JSON = "_origin_search_original_ledger_to_json"

QUERY_NOISE = {
    "career",
    "careers",
    "karriere",
    "jobs",
    "job",
    "stellenangebote",
    "offizielle",
    "karriereseite",
    "hannover",
    "germany",
    "deutschland",
    "site",
}


def _query_identity_tokens(query: str) -> tuple[str, ...]:
    folded = ascii_fold(query)
    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", folded)
        if token
        and token not in QUERY_NOISE
        and (len(token) >= 4 or (len(token) >= 3 and any(ch.isdigit() for ch in token)))
    ]
    return tuple(dict.fromkeys(tokens))


def _host_matches_query_identity(hostname: str, query: str) -> bool:
    host_compact = re.sub(r"[^a-z0-9]+", "", ascii_fold(hostname))
    if not host_compact:
        return False
    return any(
        token in host_compact
        or re.sub(r"[^a-z0-9]+", "", token) in host_compact
        for token in _query_identity_tokens(query)
    )


def _filtered_domains_from_rows(
    rows: Iterable[Mapping[str, object]],
) -> tuple[str, ...]:
    domains: list[str] = []
    for row in rows:
        normalized = adaptive_contracts.normalize_url(str(row.get("url") or ""))
        if normalized is None:
            continue
        host = str(urlparse(normalized).hostname or "").lower()
        if not host or is_followup_excluded_domain(host):
            continue
        query = str(row.get("query") or "")
        if not _host_matches_query_identity(host, query):
            continue
        if host not in domains:
            domains.append(host)
    return tuple(domains)


def install_origin_search_execution_contract() -> None:
    """Install execution patches exactly once."""

    if bool(getattr(adaptive_runtime, _INSTALL_MARKER, False)):
        return

    original_search_rows = adaptive_runtime._search_rows
    original_domains_from_rows = adaptive_runtime._domains_from_rows
    original_ledger_to_json = adaptive_contracts.SearchProgressLedger.to_json
    setattr(adaptive_runtime, _ORIGINAL_SEARCH_ROWS, original_search_rows)
    setattr(adaptive_runtime, _ORIGINAL_DOMAINS_FROM_ROWS, original_domains_from_rows)
    setattr(adaptive_contracts.SearchProgressLedger, _ORIGINAL_LEDGER_JSON, original_ledger_to_json)

    def resilient_search_rows(
        args,
        *,
        company_key: str,
        queries: Sequence[str],
        ledger: adaptive_contracts.SearchProgressLedger,
        maximum_results: int,
    ) -> tuple[list[dict[str, object]], int]:
        rows: list[dict[str, object]] = []
        requests_made = 0
        errors = list(getattr(ledger, "transport_errors", []))
        for query in queries:
            if len(rows) >= maximum_results:
                break
            try:
                part_rows, part_requests = original_search_rows(
                    args,
                    company_key=company_key,
                    queries=(query,),
                    ledger=ledger,
                    maximum_results=max(0, maximum_results - len(rows)),
                )
            except requests.RequestException as exc:
                requests_made += 1
                message = " ".join(str(exc).split())[:400]
                errors.append(
                    {
                        "query": query,
                        "failure_class": type(exc).__name__,
                        "message": message,
                        "retried": False,
                    }
                )
                print(
                    "adaptive_web_search_error: "
                    f"provider=tavily query={query} "
                    f"failure={type(exc).__name__} retried=False"
                )
                continue
            requests_made += part_requests
            rows.extend(part_rows)
        setattr(ledger, "transport_errors", errors)
        return rows, requests_made

    def ledger_to_json_with_transport_errors(
        self: adaptive_contracts.SearchProgressLedger,
    ) -> dict[str, object]:
        payload = original_ledger_to_json(self)
        errors = list(getattr(self, "transport_errors", []))
        payload["transport_errors"] = errors
        payload["transport_error_count"] = len(errors)
        payload["same_query_transport_retry"] = False
        return payload

    adaptive_runtime._search_rows = resilient_search_rows
    adaptive_runtime._domains_from_rows = _filtered_domains_from_rows
    adaptive_contracts.SearchProgressLedger.to_json = ledger_to_json_with_transport_errors
    setattr(adaptive_runtime, _INSTALL_MARKER, True)


__all__ = [
    "install_origin_search_execution_contract",
]
