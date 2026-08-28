from __future__ import annotations

import argparse
from collections import Counter
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from src.connectors.employer_origin_acquisition import (
    explicit_root_delegated_listing_hosts,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_acquisition_v4 import discover_navigation_candidates
from src.connectors.employer_origin_ats_navigation import authorized_ats_provider
from src.search_intelligence.ats_provider_registry import recognize_ats_provider

SCHEMA = "job_application_pipeline.deterministic_inventory_surface_audit.v1"
MAX_BODY_BYTES = 5_000_000
JOB_MARKERS = ("job", "jobs", "career", "careers", "karriere", "stelle", "stellen", "vacan", "recruit", "bewerb")
CLIENT_MARKERS = (
    "__next_data__",
    "/_next/static/",
    "webpack",
    "__nuxt__",
    "vite",
    "reactroot",
    "data-reactroot",
    "application/json",
    "api/",
    "graphql",
)


class SurfaceParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.iframes: list[str] = []
        self.forms: list[dict[str, str]] = []
        self.scripts: list[str] = []
        self.inline_script_fragments: list[str] = []
        self._in_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        amap = {str(k or "").casefold(): str(v or "") for k, v in attrs}
        lowered = tag.casefold()
        if lowered == "iframe":
            src = amap.get("src", "").strip()
            if src:
                self.iframes.append(urljoin(self.base_url, src))
        elif lowered == "form":
            action = amap.get("action", "").strip()
            self.forms.append(
                {
                    "method": amap.get("method", "get").strip().casefold() or "get",
                    "action": urljoin(self.base_url, action) if action else self.base_url,
                }
            )
        elif lowered == "script":
            self._in_script = True
            src = amap.get("src", "").strip()
            if src:
                self.scripts.append(urljoin(self.base_url, src))

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script and data.strip():
            self.inline_script_fragments.append(data[:4000])


def _jobish(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in JOB_MARKERS)


def _shape(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
    }


def _origin_from_layer(item: dict[str, Any]) -> str | None:
    layer = next((layer for layer in item.get("layers", []) if layer.get("layer") == "origin"), None)
    if not isinstance(layer, dict):
        return None
    evidence = layer.get("evidence") or {}
    for key in ("selected_url", "candidate_url"):
        shape = evidence.get(key)
        if not isinstance(shape, dict):
            continue
        if shape.get("query_keys"):
            return None
        scheme = str(shape.get("scheme") or "https")
        host = str(shape.get("host") or "")
        path = str(shape.get("path") or "/")
        if scheme == "https" and host:
            return f"https://{host}{path}"
    return None


def _provider_hints(urls: list[str]) -> list[str]:
    providers: list[str] = []
    for url in urls:
        recognition = recognize_ats_provider(url)
        if recognition is not None and recognition.provider not in providers:
            providers.append(recognition.provider)
    return providers


def classify_surface(item: dict[str, Any], *, html: str, final_url: str, status: int) -> dict[str, object]:
    page = parse_page(
        requested_url=final_url,
        html=html,
        final_url=final_url,
        status_code=status,
    )
    host = url_host(final_url)
    allowed_hosts = {host} if host else set()
    delegated_hosts = set(explicit_root_delegated_listing_hosts(page, allowed_hosts=allowed_hosts))
    effective_hosts = set(allowed_hosts) | delegated_hosts
    navigation = discover_navigation_candidates(page, allowed_hosts=effective_hosts, known_detail_urls=())

    parser = SurfaceParser(final_url)
    parser.feed(html)

    same_origin_jobish: list[str] = []
    external_jobish: list[str] = []
    all_external: list[str] = []
    for url, anchor_text in page.links:
        target_host = url_host(url)
        if target_host and target_host not in allowed_hosts:
            all_external.append(url)
        if not _jobish(f"{url} {anchor_text}"):
            continue
        if target_host in allowed_hosts:
            same_origin_jobish.append(url)
        elif target_host:
            external_jobish.append(url)

    iframe_jobish = [url for url in parser.iframes if _jobish(url) or recognize_ats_provider(url) is not None]
    post_forms = [form for form in parser.forms if form["method"] == "post"]
    jobish_forms = [form for form in parser.forms if _jobish(form["action"])]

    script_text = "\n".join([*parser.scripts, *parser.inline_script_fragments]).casefold()
    client_markers = sorted({marker for marker in CLIENT_MARKERS if marker in script_text or marker in html.casefold()})
    script_job_markers = sorted({marker for marker in JOB_MARKERS if marker in script_text})
    script_provider_hints = _provider_hints(parser.scripts)
    external_provider_hints = _provider_hints([*external_jobish, *parser.iframes])

    authorized_provider = authorized_ats_provider(
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=effective_hosts,
        delegated_hosts=delegated_hosts,
    )

    jsonld_count = len(re.findall(r'application/ld\+json', html, flags=re.IGNORECASE))
    jobposting_mentions = len(re.findall(r'JobPosting', html, flags=re.IGNORECASE))

    signals: list[str] = []
    if authorized_provider:
        signals.append("authorized_provider_without_executable_inventory")
    if delegated_hosts:
        signals.append("delegated_job_portal_without_executable_inventory")
    if external_jobish and not delegated_hosts:
        signals.append("external_jobish_anchor_not_promoted")
    if iframe_jobish:
        signals.append("iframe_job_or_provider_surface")
    if same_origin_jobish and not navigation:
        signals.append("same_origin_jobish_anchor_not_classified")
    if jobish_forms or post_forms:
        signals.append("form_driven_inventory_surface")
    if client_markers or script_job_markers or script_provider_hints:
        signals.append("client_rendered_or_script_inventory_surface")
    if jsonld_count or jobposting_mentions:
        signals.append("structured_job_data_present_but_not_strict")
    if not signals:
        signals.append("low_signal_inventory_surface")

    return {
        "candidate_id": item.get("candidate_id"),
        "company_key": item.get("company_key"),
        "company_name": item.get("company_name"),
        "origin": _shape(final_url),
        "status": status,
        "classification": signals[0],
        "signals": signals,
        "navigation_candidate_count": len(navigation),
        "navigation_kinds": sorted({nav.kind for nav in navigation}),
        "authorized_provider": authorized_provider,
        "delegated_hosts": sorted(delegated_hosts),
        "same_origin_jobish_anchor_count": len(set(same_origin_jobish)),
        "external_jobish_anchor_count": len(set(external_jobish)),
        "external_jobish_hosts": sorted({url_host(url) for url in external_jobish if url_host(url)}),
        "external_provider_hints": external_provider_hints,
        "iframe_jobish_count": len(set(iframe_jobish)),
        "iframe_provider_hints": _provider_hints(iframe_jobish),
        "form_count": len(parser.forms),
        "post_form_count": len(post_forms),
        "jobish_form_count": len(jobish_forms),
        "script_src_count": len(parser.scripts),
        "client_markers": client_markers,
        "script_job_markers": script_job_markers,
        "script_provider_hints": script_provider_hints,
        "jsonld_script_count": jsonld_count,
        "jobposting_mentions": jobposting_mentions,
        "body_bytes": len(html.encode("utf-8", errors="replace")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only surface audit for V2 inventory-layer failures.")
    parser.add_argument("--layer-audit", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    payload = json.loads(Path(args.layer_audit).read_text(encoding="utf-8"))
    failures = [item for item in payload.get("results", []) if item.get("first_failure_layer") == "inventory"]

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-inventory-surface-audit/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
        }
    )

    results: list[dict[str, object]] = []
    request_count = 0
    for item in failures:
        origin = _origin_from_layer(item)
        if not origin:
            results.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "company_key": item.get("company_key"),
                    "company_name": item.get("company_name"),
                    "classification": "origin_shape_not_replayable",
                    "signals": ["origin_shape_not_replayable"],
                }
            )
            continue
        try:
            response = session.get(origin, timeout=args.timeout_seconds, allow_redirects=True)
            request_count += 1
            body = response.content
            if len(body) > MAX_BODY_BYTES:
                raise RuntimeError("response body cap exceeded")
            html = body.decode(response.encoding or "utf-8", errors="replace")
            results.append(
                classify_surface(
                    item,
                    html=html,
                    final_url=str(response.url),
                    status=int(response.status_code),
                )
            )
        except requests.RequestException as exc:
            request_count += 1
            results.append(
                {
                    "candidate_id": item.get("candidate_id"),
                    "company_key": item.get("company_key"),
                    "company_name": item.get("company_name"),
                    "classification": "root_fetch_failed",
                    "signals": ["root_fetch_failed"],
                    "exception": f"{type(exc).__name__}: {exc}"[:500],
                }
            )

    primary = Counter(str(item["classification"]) for item in results)
    all_signals = Counter(signal for item in results for signal in item.get("signals", []))
    output = {
        "schema": SCHEMA,
        "boundary": {
            "input_inventory_failures": len(failures),
            "http_get_requests": request_count,
            "max_gets_per_candidate": 1,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "database_reads": 0,
            "database_writes": 0,
            "connector_materialization": 0,
        },
        "summary": {
            "inventory_failure_count": len(failures),
            "primary_classification_counts": dict(sorted(primary.items())),
            "signal_counts": dict(sorted(all_signals.items())),
        },
        "results": results,
    }
    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    print("============================================")
    print("DETERMINISTIC INVENTORY SURFACE AUDIT")
    print("============================================")
    print(f"inventory_failure_count={len(failures)}")
    print("primary_classification_counts=" + json.dumps(dict(sorted(primary.items())), sort_keys=True))
    print("signal_counts=" + json.dumps(dict(sorted(all_signals.items())), sort_keys=True))
    print()
    for item in results:
        print(f"{str(item.get('candidate_id')):>3} | {item.get('company_key')} | {item.get('company_name')}")
        print(f"  class={item.get('classification')}")
        print("  signals=" + ", ".join(str(signal) for signal in item.get("signals", [])))
        print(
            "  provider=" + str(item.get("authorized_provider"))
            + " nav=" + str(item.get("navigation_candidate_count"))
            + " same_jobish=" + str(item.get("same_origin_jobish_anchor_count"))
            + " external_jobish=" + str(item.get("external_jobish_anchor_count"))
            + " iframe=" + str(item.get("iframe_jobish_count"))
            + " forms=" + str(item.get("form_count"))
        )
    print()
    print(f"HTTP_GET_REQUESTS={request_count}")
    print("PROVIDER_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print(f"artifact={args.output}")
    print("INVENTORY_SURFACE_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
