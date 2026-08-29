from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse

import requests

from scripts.run_deterministic_inventory_surface_audit import _origin_from_layer
from src.connectors.employer_origin_acquisition import (
    canonical_url,
    explicit_root_delegated_listing_hosts,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_acquisition_v4 import (
    acquire_genuine_job_pages,
    discover_navigation_candidates,
)
from src.search_intelligence.ats_provider_registry import (
    classify_provider_names,
    recognize_ats_provider,
)
from src.search_intelligence.connector_feasibility_query_runtime import (
    QUERY_DETAIL_ACTION_KEYS,
    QUERY_JOB_IDENTIFIER_KEYS,
    QUERY_ROUTE_CONTEXT_KEYS,
    QUERY_SCOPE_KEYS,
    extract_trusted_query_job_detail_links,
)

SCHEMA = "job_application_pipeline.deterministic_detail_surface_audit.v1"
MAX_BODY_BYTES = 5_000_000
ABSOLUTE_GET_CAP = 4

JOB_MARKERS = (
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "stelle",
    "stellen",
    "vacan",
    "recruit",
    "bewerb",
)
CLIENT_MARKERS = (
    "__next_data__",
    "/_next/static/",
    "webpack",
    "__nuxt__",
    "vite",
    "reactroot",
    "data-reactroot",
    "graphql",
    "api/",
)
IDENTIFIERISH_KEY_MARKERS = (
    "id",
    "object",
    "req",
    "requisition",
    "vacan",
    "position",
    "posting",
    "opening",
)
FILTER_OR_PAGING_KEYS = {
    "page",
    "pagesize",
    "pageindex",
    "offset",
    "start",
    "limit",
    "sort",
    "orderby",
    "order",
    "search",
    "q",
    "query",
    "keyword",
    "keywords",
    "location",
    "country",
    "city",
    "category",
    "department",
    "brand",
    "locale",
    "language",
    "lang",
}


def _normalized_query_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _known_query_keys() -> set[str]:
    values = {
        *QUERY_JOB_IDENTIFIER_KEYS,
        *QUERY_SCOPE_KEYS,
        *QUERY_DETAIL_ACTION_KEYS,
        *QUERY_ROUTE_CONTEXT_KEYS,
        *FILTER_OR_PAGING_KEYS,
    }
    return {_normalized_query_key(value) for value in values}


def _identifierish_unknown_key(value: str) -> bool:
    normalized = _normalized_query_key(value)
    if not normalized or normalized in _known_query_keys():
        return False
    return any(marker in normalized for marker in IDENTIFIERISH_KEY_MARKERS)


def _jobish(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in JOB_MARKERS)


def _shape(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
        "query_keys": sorted({key for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}),
    }


class _StructuralParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.forms: list[dict[str, object]] = []
        self.scripts: list[str] = []
        self._form_stack: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        amap = {str(key or "").casefold(): str(value or "") for key, value in attrs}
        lowered = tag.casefold()
        if lowered == "form":
            action = amap.get("action", "").strip()
            frame: dict[str, object] = {
                "method": amap.get("method", "get").strip().casefold() or "get",
                "action": _shape(urljoin(self.base_url, action) if action else self.base_url),
                "field_names": [],
            }
            self._form_stack.append(frame)
            self.forms.append(frame)
            return
        if lowered in {"input", "select", "textarea", "button"} and self._form_stack:
            name = amap.get("name", "").strip()
            if name:
                fields = self._form_stack[-1]["field_names"]
                assert isinstance(fields, list)
                if name not in fields:
                    fields.append(name)
            return
        if lowered == "script":
            src = amap.get("src", "").strip()
            if src:
                self.scripts.append(urljoin(self.base_url, src))

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "form" and self._form_stack:
            self._form_stack.pop()


def classify_detail_surface(*, page_url: str, html: str, status: int) -> dict[str, object]:
    page = parse_page(
        requested_url=page_url,
        html=html,
        final_url=page_url,
        status_code=status,
    )
    host = url_host(page_url)
    allowed_hosts = {host} if host else set()
    navigation = discover_navigation_candidates(
        page,
        allowed_hosts=allowed_hosts,
        known_detail_urls=(),
    )
    current_detail_urls = {item.url for item in navigation if item.kind == "detail"}
    trusted_query = extract_trusted_query_job_detail_links(page_url, html)
    trusted_query_urls = {item.url for item in trusted_query}

    unknown_identifier_keys: Counter[str] = Counter()
    unclassified_jobish = 0
    for url, label in page.links:
        parsed = urlparse(url)
        if not parsed.query:
            if _jobish(f"{url} {label}") and url not in current_detail_urls:
                unclassified_jobish += 1
            continue
        surface = f"{url} {label}"
        if not _jobish(surface) and not _jobish(page_url):
            continue
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
            if _identifierish_unknown_key(key):
                unknown_identifier_keys[_normalized_query_key(key)] += 1
        if url not in current_detail_urls and url not in trusted_query_urls:
            unclassified_jobish += 1

    parser = _StructuralParser(page_url)
    parser.feed(html)

    form_detail_signal = False
    for form in parser.forms:
        action = form.get("action") or {}
        action_surface = f"{action.get('host', '')}{action.get('path', '')}" if isinstance(action, dict) else ""
        fields = [str(value) for value in form.get("field_names", [])]
        if _jobish(action_surface) or any(
            _identifierish_unknown_key(field) or _jobish(field)
            for field in fields
        ):
            form_detail_signal = True
            break

    script_surface = "\n".join(parser.scripts) + "\n" + html[:500_000]
    client_markers = sorted({marker for marker in CLIENT_MARKERS if marker in script_surface.casefold()})
    script_job_markers = sorted({marker for marker in JOB_MARKERS if marker in script_surface.casefold()})

    direct_recognition = recognize_ats_provider(page_url)
    provider_hints = set(classify_provider_names(html[:500_000]))
    if direct_recognition is not None:
        provider_hints.add(direct_recognition.provider)

    if trusted_query:
        classification = "strict_query_detail_already_visible"
    elif unknown_identifier_keys:
        classification = "unknown_query_identifier_key_surface"
    elif form_detail_signal:
        classification = "form_driven_detail_surface"
    elif unclassified_jobish:
        classification = "unclassified_jobish_detail_surface"
    elif client_markers or script_job_markers:
        classification = "client_rendered_or_script_detail_surface"
    elif provider_hints:
        classification = "provider_detail_route_gap"
    else:
        classification = "low_signal_detail_surface"

    return {
        "page": _shape(page_url),
        "status": status,
        "classification": classification,
        "current_navigation_candidate_count": len(navigation),
        "current_detail_candidate_count": len(current_detail_urls),
        "trusted_query_detail_count": len(trusted_query),
        "unknown_identifier_query_keys": dict(sorted(unknown_identifier_keys.items())),
        "unclassified_jobish_anchor_count": unclassified_jobish,
        "form_count": len(parser.forms),
        "form_detail_signal": form_detail_signal,
        "forms": parser.forms[:10],
        "script_src_count": len(parser.scripts),
        "client_markers": client_markers,
        "script_job_markers": script_job_markers,
        "provider_hints": sorted(provider_hints),
    }


def _primary_classification(page_summaries: list[dict[str, object]]) -> str:
    priority = (
        "strict_query_detail_already_visible",
        "unknown_query_identifier_key_surface",
        "form_driven_detail_surface",
        "unclassified_jobish_detail_surface",
        "client_rendered_or_script_detail_surface",
        "provider_detail_route_gap",
        "low_signal_detail_surface",
    )
    observed = {str(item.get("classification") or "") for item in page_summaries}
    return next((value for value in priority if value in observed), "low_signal_detail_surface")


def _audit_case(item: dict[str, Any], *, timeout_seconds: float) -> dict[str, object]:
    origin = _origin_from_layer(item)
    if not origin:
        return {
            "candidate_id": item.get("candidate_id"),
            "company_key": item.get("company_key"),
            "company_name": item.get("company_name"),
            "classification": "origin_shape_not_replayable",
            "request_count": 0,
            "page_summaries": [],
        }

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-detail-surface-audit/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )
    cache: dict[str, tuple[str, str, int]] = {}
    calls: list[dict[str, object]] = []
    fetched_pages: list[tuple[str, str, int]] = []

    def fetcher(url: str) -> tuple[str, str, int]:
        clean = canonical_url(url)
        if clean in cache:
            return cache[clean]
        if len(calls) >= ABSOLUTE_GET_CAP:
            raise RuntimeError("absolute detail audit GET cap exceeded")
        parsed = urlparse(url)
        if parsed.scheme.casefold() != "https" or not parsed.hostname:
            raise RuntimeError("detail audit permits HTTPS GET only")
        response = session.get(url, timeout=timeout_seconds, allow_redirects=True)
        body = response.content
        if len(body) > MAX_BODY_BYTES:
            raise RuntimeError("response body cap exceeded")
        text = body.decode(response.encoding or "utf-8", errors="replace")
        result = (text, str(response.url), int(response.status_code))
        calls.append(
            {
                "requested": _shape(url),
                "final": _shape(str(response.url)),
                "status": int(response.status_code),
                "body_bytes": len(body),
            }
        )
        fetched_pages.append((str(response.url), text, int(response.status_code)))
        cache[clean] = result
        cache[canonical_url(str(response.url))] = result
        return result

    replay_error: str | None = None
    current_v4_resolved = False
    try:
        root_html, root_final_url, root_status = fetcher(origin)
        if root_status >= 400:
            raise RuntimeError(f"root status {root_status}")
        initial_host = url_host(origin)
        final_host = url_host(root_final_url)
        allowed_hosts = {host for host in (initial_host, final_host) if host}
        root = parse_page(
            requested_url=origin,
            html=root_html,
            final_url=root_final_url,
            status_code=root_status,
        )
        allowed_hosts.update(explicit_root_delegated_listing_hosts(root, allowed_hosts=allowed_hosts))
        jobs, _observed_root = acquire_genuine_job_pages(
            listing_url=origin,
            allowed_hosts=tuple(sorted(allowed_hosts)),
            known_detail_urls=(),
            fetcher=fetcher,
            max_followup_requests=2,
            max_results=1,
        )
        current_v4_resolved = bool(jobs)
    except Exception as exc:
        replay_error = f"{type(exc).__name__}: {exc}"[:500]

    page_summaries = [
        classify_detail_surface(page_url=url, html=html, status=status)
        for url, html, status in fetched_pages
    ]
    classification = (
        "current_v4_now_resolves_detail"
        if current_v4_resolved
        else _primary_classification(page_summaries)
    )
    return {
        "candidate_id": item.get("candidate_id"),
        "company_key": item.get("company_key"),
        "company_name": item.get("company_name"),
        "origin": _shape(origin),
        "classification": classification,
        "current_v4_now_resolves_detail": current_v4_resolved,
        "request_count": len(calls),
        "requests": calls,
        "replay_error": replay_error,
        "page_summaries": page_summaries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only structural audit for V5 detail-layer residuals.")
    parser.add_argument("--layer-audit", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    payload = json.loads(Path(args.layer_audit).read_text(encoding="utf-8"))
    failures = [
        item
        for item in payload.get("results", [])
        if item.get("first_failure_layer") == "detail"
    ]

    results = [_audit_case(item, timeout_seconds=args.timeout_seconds) for item in failures]
    classification_counts = Counter(str(item["classification"]) for item in results)
    request_count = sum(int(item.get("request_count") or 0) for item in results)

    output = {
        "schema": SCHEMA,
        "boundary": {
            "input_detail_failures": len(failures),
            "http_get_requests": request_count,
            "max_gets_per_candidate": ABSOLUTE_GET_CAP,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "database_reads": 0,
            "database_writes": 0,
            "connector_materialization": 0,
            "query_values_persisted": 0,
        },
        "summary": {
            "detail_failure_count": len(failures),
            "classification_counts": dict(sorted(classification_counts.items())),
        },
        "results": results,
    }
    Path(args.output).write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("DETERMINISTIC DETAIL SURFACE AUDIT")
    print("============================================")
    print(f"detail_failure_count={len(failures)}")
    print("classification_counts=" + json.dumps(dict(sorted(classification_counts.items())), sort_keys=True))
    print()
    for item in results:
        print(f"{str(item.get('candidate_id')):>3} | {item.get('company_key')} | {item.get('company_name')}")
        print(f"  classification={item.get('classification')} requests={item.get('request_count')}")
        if item.get("replay_error"):
            print(f"  replay_error={item.get('replay_error')}")
        for page in item.get("page_summaries", []):
            shape = page.get("page") or {}
            print(
                "    - "
                + str(shape.get("host"))
                + str(shape.get("path"))
                + " class=" + str(page.get("classification"))
                + " unknown_keys=" + json.dumps(page.get("unknown_identifier_query_keys") or {}, sort_keys=True)
                + " unclassified=" + str(page.get("unclassified_jobish_anchor_count"))
                + " forms=" + str(page.get("form_count"))
                + " client=" + str(bool(page.get("client_markers")))
                + " providers=" + ",".join(str(value) for value in page.get("provider_hints", []))
            )
    print()
    print(f"HTTP_GET_REQUESTS={request_count}")
    print("PROVIDER_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print("QUERY_VALUES_PERSISTED=0")
    print(f"artifact={args.output}")
    print("DETAIL_SURFACE_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
