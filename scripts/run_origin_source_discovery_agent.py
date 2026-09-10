"""Run read-only origin source discovery for employer-origin candidates.

This agent is a safer successor to pure URL recovery. It probes bounded URL
candidates but only selects URLs that are both career/job-like and plausibly
matched to the company identity. F1 extends the same authority with optional
official-domain evidence and bounded official-page career/ATS link discovery. It
never writes candidate_url, never builds/registers connectors and never changes
schedules.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlencode

import psycopg
from psycopg.rows import dict_row
import requests

from src.config import get_database_config
from src.search_intelligence.official_domain_evidence import (
    OfficialDomainEvidence,
    resolve_wikidata_official_domains,
)
from src.search_intelligence.origin_jobspace_discovery import (
    FetchedOriginPage,
    discover_official_origin_jobspace,
)
from src.search_intelligence.origin_source_discovery_agent import (
    OriginDiscoveryProbeResult,
    OriginSearchResult,
    generate_search_query_hints,
    probe_result_from_http_response,
    result_to_json,
)

BOUNDARY = (
    "read-only",
    "no candidate_url write",
    "no connector registration",
    "no source activation",
    "no Bronze/Silver write",
    "no scheduler change",
    "official-domain evidence never bypasses company identity or proof",
)
HTTP_USER_AGENT = (
    "job-application-pipeline-origin-source-discovery/0.2 "
    "(+bounded personal portfolio project)"
)
MAX_HTTP_BODY_BYTES = 5_000_000


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_candidate(conn: psycopg.Connection[Any], company_key: str) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                company_key,
                company_name,
                candidate_url,
                source_family_candidate,
                status,
                risk_level
            FROM employer_origin_source_candidates
            WHERE company_key = %s
            ORDER BY updated_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (company_key,),
        )
        row = cur.fetchone()
    if row is None:
        raise SystemExit(f"No employer-origin candidate found for company_key={company_key!r}.")
    return dict(row)


def load_market_evidence_urls(conn: psycopg.Connection[Any], company_key: str, *, limit: int) -> list[str]:
    urls: list[str] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT evidence_url
            FROM market_evidence
            WHERE normalized_company_key = %s
              AND evidence_url IS NOT NULL
            ORDER BY observed_at DESC NULLS LAST, created_at DESC
            LIMIT %s
            """,
            (company_key, limit),
        )
        for row in cur.fetchall():
            if row.get("evidence_url"):
                urls.append(str(row["evidence_url"]))
    return urls


def _json_search_result_rows(payload: object, *, company_key: str) -> Iterable[dict[str, object]]:
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                if not item.get("company_key") or str(item.get("company_key")) == company_key:
                    yield item
        return
    if not isinstance(payload, dict):
        return
    if company_key in payload and isinstance(payload[company_key], list):
        for item in payload[company_key]:
            if isinstance(item, dict):
                yield item
    for key in ("results", "items"):
        if isinstance(payload.get(key), list):
            for item in payload[key]:
                if isinstance(item, dict) and (not item.get("company_key") or str(item.get("company_key")) == company_key):
                    yield item


def load_search_results_json(path: Path, *, company_key: str) -> list[OriginSearchResult]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    results: list[OriginSearchResult] = []
    for row in _json_search_result_rows(payload, company_key=company_key):
        url = str(row.get("url") or row.get("link") or "").strip()
        if not url:
            continue
        results.append(
            OriginSearchResult(
                url=url,
                title=str(row.get("title") or ""),
                snippet=str(row.get("snippet") or row.get("content") or row.get("description") or ""),
                query=str(row.get("query") or ""),
                provider=str(row.get("provider") or "json"),
            )
        )
    return results


def load_local_env_file(path: str = ".env") -> None:
    """Load simple KEY=VALUE entries from .env without overriding existing env vars."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and (key not in os.environ or _is_missing_or_placeholder_secret(os.environ.get(key))):
            os.environ[key] = value


def _is_missing_or_placeholder_secret(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip()
    lowered = normalized.lower()
    return (
        normalized == ""
        or normalized == "..."
        or "your_api_key" in lowered
        or "api_key" in lowered
        or "realer_key" in lowered
        or "hier" in lowered
        or normalized in {"<YOUR_API_KEY>", "YOUR_API_KEY", "changeme"}
    )


def _response_json_or_empty(response: requests.Response) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _http_error_to_warning(provider: str, exc: requests.HTTPError) -> None:
    status = exc.response.status_code if exc.response is not None else "unknown"
    body = ""
    if exc.response is not None:
        body = (exc.response.text or "")[:300].replace("\n", " ")
    print(f"web_search_warning: provider_http_error provider={provider} status={status} reason={body}", file=sys.stderr)


def tavily_search(query: str, *, max_results: int, timeout_seconds: float, search_depth: str) -> list[OriginSearchResult]:
    api_key = os.getenv("TAVILY_API_KEY")
    if _is_missing_or_placeholder_secret(api_key):
        print("web_search_warning: provider=tavily reason=missing_or_placeholder_api_key", file=sys.stderr)
        return []

    response = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "query": query,
            "search_depth": search_depth,
            "max_results": max(1, min(max_results, 10)),
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=timeout_seconds,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        _http_error_to_warning("tavily", exc)
        return []

    payload = _response_json_or_empty(response)
    return [
        OriginSearchResult(
            url=str(item.get("url") or ""),
            title=str(item.get("title") or ""),
            snippet=str(item.get("content") or ""),
            query=query,
            provider="tavily",
        )
        for item in payload.get("results", [])
        if isinstance(item, dict) and item.get("url")
    ]


def brave_search(query: str, *, max_results: int, timeout_seconds: float) -> list[OriginSearchResult]:
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")
    if _is_missing_or_placeholder_secret(api_key):
        print("web_search_warning: provider=brave reason=missing_or_placeholder_api_key", file=sys.stderr)
        return []

    params = urlencode(
        {
            "q": query,
            "count": max(1, min(max_results, 20)),
            "country": "DE",
            "search_lang": "de",
            "ui_lang": "de-DE",
        }
    )
    response = requests.get(
        f"https://api.search.brave.com/res/v1/web/search?{params}",
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
        timeout=timeout_seconds,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        _http_error_to_warning("brave", exc)
        return []

    payload = _response_json_or_empty(response)
    return [
        OriginSearchResult(
            url=str(item.get("url") or ""),
            title=str(item.get("title") or ""),
            snippet=str(item.get("description") or ""),
            query=query,
            provider="brave",
        )
        for item in payload.get("web", {}).get("results", [])
        if isinstance(item, dict) and item.get("url")
    ]


def google_cse_search(query: str, *, max_results: int, timeout_seconds: float) -> list[OriginSearchResult]:
    api_key = os.getenv("GOOGLE_CSE_API_KEY")
    cx = os.getenv("GOOGLE_CSE_CX")
    if _is_missing_or_placeholder_secret(api_key) or _is_missing_or_placeholder_secret(cx):
        print("web_search_warning: provider=google_cse reason=missing_or_placeholder_api_key_or_cx", file=sys.stderr)
        return []

    params = urlencode({"key": api_key, "cx": cx, "q": query, "num": max(1, min(max_results, 10))})
    response = requests.get(f"https://www.googleapis.com/customsearch/v1?{params}", timeout=timeout_seconds)

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        _http_error_to_warning("google_cse", exc)
        return []

    payload = _response_json_or_empty(response)
    return [
        OriginSearchResult(
            url=str(item.get("link") or ""),
            title=str(item.get("title") or ""),
            snippet=str(item.get("snippet") or ""),
            query=query,
            provider="google_cse",
        )
        for item in payload.get("items", [])
        if isinstance(item, dict) and item.get("link")
    ]


def web_search(query: str, *, provider: str, max_results: int, timeout_seconds: float, search_depth: str) -> list[OriginSearchResult]:
    if provider == "tavily":
        return tavily_search(query, max_results=max_results, timeout_seconds=timeout_seconds, search_depth=search_depth)
    if provider in {"brave", "google_cse"}:
        print(f"web_search_warning: provider={provider} reason=provider_disabled_use_tavily", file=sys.stderr)
        return []
    print(f"web_search_warning: unsupported_provider provider={provider}", file=sys.stderr)
    return []


def collect_search_results(args: argparse.Namespace, *, company_key: str, company_name: str) -> list[OriginSearchResult]:
    results: list[OriginSearchResult] = []
    if args.search_results_json:
        results.extend(load_search_results_json(Path(args.search_results_json), company_key=company_key))

    providers = [provider for provider in args.search_provider if provider != "none"]
    if not providers:
        return results

    queries = list(generate_search_query_hints(company_name=company_name, company_key=company_key, target_location=args.target_location))[: args.search_query_limit]
    for provider in providers:
        for query in queries:
            print(f"web_search: provider={provider} query={query}", file=sys.stderr)
            results.extend(
                web_search(
                    query,
                    provider=provider,
                    max_results=args.search_max_results,
                    timeout_seconds=args.search_timeout_seconds,
                    search_depth=args.search_depth,
                )
            )
    return results


class HttpDiscoveryClient:
    """Bounded cache shared by score probes and official-page surface reads."""

    def __init__(self, *, timeout_seconds: float, max_requests: int = 48) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_requests = max_requests
        self.request_count = 0
        self._responses: dict[str, requests.Response | None] = {}

    def _get(self, url: str) -> requests.Response | None:
        if url in self._responses:
            return self._responses[url]
        if self.request_count >= self.max_requests:
            self._responses[url] = None
            return None
        self.request_count += 1
        try:
            response = requests.get(
                url,
                timeout=self.timeout_seconds,
                headers={
                    "User-Agent": HTTP_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                allow_redirects=True,
            )
        except requests.RequestException:
            response = None
        self._responses[url] = response
        return response

    def probe(self, url: str) -> OriginDiscoveryProbeResult:
        response = self._get(url)
        if response is None:
            return OriginDiscoveryProbeResult(
                url=url,
                final_url=None,
                status_code=None,
                reachable=False,
                career_like=False,
                reason="request failed or F1 HTTP request cap reached",
            )
        return probe_result_from_http_response(url, response)

    def fetch_page(self, url: str) -> FetchedOriginPage:
        response = self._get(url)
        if response is None:
            return FetchedOriginPage(url, url, 599, "")
        body = response.content or b""
        if len(body) > MAX_HTTP_BODY_BYTES:
            return FetchedOriginPage(url, str(response.url), 598, "")
        return FetchedOriginPage(
            requested_url=url,
            final_url=str(response.url),
            status_code=int(response.status_code),
            html=response.text,
        )


def http_probe(url: str, *, timeout_seconds: float) -> OriginDiscoveryProbeResult:
    """Compatibility helper retained for existing tests/callers."""

    return HttpDiscoveryClient(timeout_seconds=timeout_seconds, max_requests=1).probe(url)


def _wikidata_request_json(
    url: str,
    params: Mapping[str, str],
    *,
    timeout_seconds: float,
) -> Mapping[str, object]:
    response = requests.get(
        url,
        params=dict(params),
        timeout=timeout_seconds,
        headers={
            "User-Agent": HTTP_USER_AGENT,
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def collect_official_domain_evidence(
    args: argparse.Namespace,
    *,
    company_name: str,
) -> list[OfficialDomainEvidence]:
    evidence: list[OfficialDomainEvidence] = []
    for url in args.official_domain_url:
        normalized = str(url or "").strip()
        if normalized:
            evidence.append(
                OfficialDomainEvidence(
                    url=normalized,
                    provider="operator_supplied",
                    entity_id="",
                    entity_label=company_name,
                    entity_description="operator-supplied official-domain candidate",
                )
            )

    if args.official_domain_provider == "wikidata":
        try:
            evidence.extend(
                resolve_wikidata_official_domains(
                    company_name,
                    request_json=lambda url, params: _wikidata_request_json(
                        url,
                        params,
                        timeout_seconds=args.official_domain_timeout_seconds,
                    ),
                )
            )
        except (requests.RequestException, ValueError, TypeError) as exc:
            print(
                "official_domain_warning: provider=wikidata "
                f"reason={exc.__class__.__name__}",
                file=sys.stderr,
            )

    unique: list[OfficialDomainEvidence] = []
    seen: set[str] = set()
    for item in evidence:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    return unique


def run_for_company(args: argparse.Namespace, company_key: str) -> dict[str, object]:
    with connect() as conn:
        candidate = load_candidate(conn, company_key)
        market_urls = load_market_evidence_urls(conn, company_key, limit=args.market_evidence_limit)

    company_name = str(candidate["company_name"])
    search_results = collect_search_results(
        args,
        company_key=str(candidate["company_key"]),
        company_name=company_name,
    )
    official_evidence = collect_official_domain_evidence(
        args,
        company_name=company_name,
    )

    http = None if args.no_probe else HttpDiscoveryClient(
        timeout_seconds=args.timeout_seconds,
        max_requests=args.http_request_cap,
    )
    expanded = discover_official_origin_jobspace(
        company_key=str(candidate["company_key"]),
        company_name=company_name,
        source_family_candidate=str(candidate.get("source_family_candidate") or ""),
        market_evidence_urls=market_urls,
        search_results=search_results,
        official_domain_urls=[item.url for item in official_evidence],
        target_location=args.target_location,
        probe=None if http is None else http.probe,
        fetch_page=(
            None
            if http is None or args.no_surface_expansion
            else http.fetch_page
        ),
        max_generated_candidates=args.max_candidates,
    )
    payload = result_to_json(expanded.origin)
    payload["candidate_id"] = candidate["id"]
    payload["candidate_status"] = candidate.get("status")
    payload["candidate_risk_level"] = candidate.get("risk_level")
    payload["candidate_url_before"] = candidate.get("candidate_url")
    payload["market_evidence_url_count"] = len(market_urls)
    payload["search_result_count"] = len(search_results)
    payload["search_provider"] = ",".join(provider for provider in args.search_provider if provider != "none") or "none"
    payload["search_results"] = [
        {
            "provider": item.provider,
            "query": item.query,
            "title": item.title,
            "url": item.url,
        }
        for item in search_results
    ]
    payload["probe_enabled"] = not args.no_probe
    payload["f1_initial_decision"] = expanded.initial.decision
    payload["f1_surface_page_count"] = expanded.surface_page_count
    payload["f1_discovered_jobspace_url_count"] = expanded.discovered_jobspace_url_count
    payload["f1_ats_families"] = list(expanded.ats_families)
    payload["f1_official_domain_evidence_count"] = expanded.official_domain_evidence_count
    payload["f1_official_domain_provider"] = args.official_domain_provider
    payload["f1_official_domain_evidence"] = [
        {
            "url": item.url,
            "provider": item.provider,
            "entity_id": item.entity_id,
            "entity_label": item.entity_label,
            "entity_description": item.entity_description,
            "property_id": item.property_id,
        }
        for item in official_evidence
    ]
    payload["f1_http_request_count"] = 0 if http is None else http.request_count
    payload["f1_surface_expansion_enabled"] = not args.no_surface_expansion and http is not None
    return payload


def print_result(payload: dict[str, object]) -> None:
    print("Origin Source Discovery Agent v4 / F1 jobspace expansion")
    print("boundary: " + ", ".join(BOUNDARY))
    print("---")
    for key in (
        "candidate_id",
        "company_key",
        "company_name",
        "candidate_status",
        "candidate_risk_level",
        "candidate_url_before",
        "decision",
        "selected_url",
        "selected_domain",
        "confidence_score",
        "risk_level",
        "reason",
        "candidate_count",
        "assessed_count",
        "market_evidence_url_count",
        "search_result_count",
        "search_provider",
        "probe_enabled",
        "f1_initial_decision",
        "f1_official_domain_provider",
        "f1_official_domain_evidence_count",
        "f1_surface_page_count",
        "f1_discovered_jobspace_url_count",
        "f1_ats_families",
        "f1_http_request_count",
        "f1_surface_expansion_enabled",
    ):
        print(f"{key}: {payload.get(key)}")

    print("---")
    print("alternatives:")
    for item in payload.get("alternatives", [])[:8]:
        print(
            "- "
            f"{item.get('url')} | decision={item.get('decision')} | "
            f"score={item.get('total_score')} | identity={item.get('identity_score')} | "
            f"career={item.get('career_score')} | domain={item.get('domain')} | "
            f"reasons={'; '.join(str(reason) for reason in item.get('reasons', []))}"
        )

    print("---")
    print("rejected:")
    for item in payload.get("rejected", [])[:8]:
        print(
            "- "
            f"{item.get('url')} | decision={item.get('decision')} | "
            f"score={item.get('total_score')} | domain={item.get('domain')} | "
            f"reasons={'; '.join(str(reason) for reason in item.get('reasons', []))}"
        )

    print("---")
    official_evidence = payload.get("f1_official_domain_evidence", [])
    if official_evidence:
        print("official_domain_evidence:")
        for item in official_evidence[:8]:
            print(
                f"- {item.get('provider')} | {item.get('entity_id')} | "
                f"{item.get('entity_label')} | {item.get('url')}"
            )

    search_results = payload.get("search_results", [])
    if search_results:
        print("search_results:")
        for item in search_results[:12]:
            print(
                f"- {item.get('provider')} | {item.get('query')} | "
                f"{item.get('title')} | {item.get('url')}"
            )

    print("search_query_hints:")
    for query in payload.get("search_query_hints", []):
        print(f"- {query}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run read-only origin-source discovery for employer-origin candidates.")
    parser.add_argument("--company-key", action="append", required=True, help="Company key to inspect. Repeat for multiple candidates.")
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--reviewed-by", default="agent")
    parser.add_argument("--timeout-seconds", type=float, default=6.0)
    parser.add_argument("--http-request-cap", type=int, default=48)
    parser.add_argument("--max-candidates", type=int, default=30)
    parser.add_argument("--market-evidence-limit", type=int, default=20)
    parser.add_argument(
        "--search-provider",
        action="append",
        default=["none"],
        choices=("none", "tavily"),
        help="Optional web-search provider. Repeat to query multiple providers. Default: none.",
    )
    parser.add_argument("--search-query-limit", type=int, default=4)
    parser.add_argument("--search-max-results", type=int, default=5)
    parser.add_argument("--search-timeout-seconds", type=float, default=8.0)
    parser.add_argument("--search-depth", default="basic", choices=("basic", "advanced"))
    parser.add_argument(
        "--search-results-json",
        help="Optional offline search-result JSON file for replay/validation without external API calls.",
    )
    parser.add_argument(
        "--official-domain-provider",
        default="none",
        choices=("none", "wikidata"),
        help="Optional fail-soft official-domain evidence provider. Never bypasses JAP proof.",
    )
    parser.add_argument(
        "--official-domain-url",
        action="append",
        default=[],
        help="Optional explicit official-domain candidate evidence. Repeat as needed.",
    )
    parser.add_argument("--official-domain-timeout-seconds", type=float, default=8.0)
    parser.add_argument(
        "--no-surface-expansion",
        action="store_true",
        help="Disable bounded extraction of career/ATS links from plausible official pages.",
    )
    parser.add_argument("--no-probe", action="store_true", help="Only score generated/evidence/search URLs without HTTP probing.")
    parser.add_argument("--json", action="store_true", help="Print JSON payload instead of human-readable output.")
    return parser


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    if len(args.search_provider) > 1 and "none" in args.search_provider:
        args.search_provider = [provider for provider in args.search_provider if provider != "none"]
    payloads = [run_for_company(args, key) for key in args.company_key]
    if args.json:
        print(json.dumps(payloads, indent=2, ensure_ascii=False, sort_keys=True))
        return
    for index, payload in enumerate(payloads):
        if index:
            print()
            print("=" * 120)
        print_result(payload)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
