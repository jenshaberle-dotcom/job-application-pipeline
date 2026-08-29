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


SCHEMA = "job_application_pipeline.deterministic_successfactors_search_carrier_audit.v1"
MAX_BODY_BYTES = 5_000_000
SEARCH_SCRIPT_PATH = "/platform/js/search/search.js"
_SEARCH_ROUTE_LITERAL = re.compile(
    r"(?P<quote>[\"'])(?P<route>/search/?(?:\?[^\"']*)?)(?P=quote)",
    flags=re.IGNORECASE,
)
_GET_METHOD = re.compile(
    r"(?:\b(?:type|method)\s*:\s*[\"']GET[\"']|\$\s*\.\s*get\s*\()",
    flags=re.IGNORECASE,
)
_POST_METHOD = re.compile(
    r"(?:\b(?:type|method)\s*:\s*[\"']POST[\"']|\$\s*\.\s*post\s*\()",
    flags=re.IGNORECASE,
)


def _host(value: str) -> str:
    return (urlparse(value).hostname or "").casefold().strip(".")


def _safe_url_shape(url: str) -> dict[str, object]:
    parsed = urlparse(url)
    return {
        "scheme": parsed.scheme.casefold(),
        "host": (parsed.hostname or "").casefold(),
        "path": parsed.path or "/",
        "query_keys": sorted({key for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}),
    }


def _same_https_host(left: str, right: str) -> bool:
    parsed = urlparse(right)
    return parsed.scheme.casefold() == "https" and bool(_host(left)) and _host(left) == _host(right)


class _RootCarrierParser(HTMLParser):
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
            action = urljoin(self.base_url, amap.get("action", "").strip() or self.base_url)
            frame: dict[str, object] = {
                "method": amap.get("method", "get").strip().casefold() or "get",
                "action_url": action,
                "field_names": [],
            }
            self._form_stack.append(frame)
            self.forms.append(frame)
            return
        if lowered in {"input", "select", "textarea", "button"} and self._form_stack:
            name = amap.get("name", "").strip()
            fields = self._form_stack[-1].get("field_names")
            if name and isinstance(fields, list) and name not in fields:
                fields.append(name)
            return
        if lowered == "script":
            src = amap.get("src", "").strip()
            if src:
                self.scripts.append(urljoin(self.base_url, src))

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "form" and self._form_stack:
            self._form_stack.pop()


def explicit_root_get_search_forms(page_url: str, html: str) -> tuple[dict[str, object], ...]:
    parser = _RootCarrierParser(page_url)
    parser.feed(html)
    result: list[dict[str, object]] = []
    for form in parser.forms:
        action_url = str(form.get("action_url") or "")
        if str(form.get("method") or "").casefold() != "get":
            continue
        if not _same_https_host(page_url, action_url):
            continue
        path = urlparse(action_url).path.rstrip("/").casefold()
        if path != "/search":
            continue
        fields = form.get("field_names")
        result.append(
            {
                "method": "get",
                "action": _safe_url_shape(action_url),
                "field_names": sorted(str(value) for value in fields) if isinstance(fields, list) else [],
            }
        )
    return tuple(result)


def explicit_same_host_search_scripts(page_url: str, html: str) -> tuple[str, ...]:
    parser = _RootCarrierParser(page_url)
    parser.feed(html)
    result: list[str] = []
    seen: set[str] = set()
    for script_url in parser.scripts:
        parsed = urlparse(script_url)
        if not _same_https_host(page_url, script_url):
            continue
        if parsed.path.rstrip("/").casefold() != SEARCH_SCRIPT_PATH.casefold():
            continue
        normalized = script_url.split("#", 1)[0]
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def classify_search_script(script_body: str) -> dict[str, object]:
    route_shapes: list[dict[str, object]] = []
    strict_get_routes: list[dict[str, object]] = []
    post_near_route = False
    seen: set[tuple[str, tuple[str, ...]]] = set()

    for match in _SEARCH_ROUTE_LITERAL.finditer(script_body):
        raw_route = match.group("route")
        shape = _safe_url_shape(f"https://carrier.invalid{raw_route}")
        key = (str(shape["path"]), tuple(str(value) for value in shape["query_keys"]))
        if key not in seen:
            seen.add(key)
            route_shapes.append({"path": shape["path"], "query_keys": shape["query_keys"]})

        start = max(0, match.start() - 350)
        end = min(len(script_body), match.end() + 350)
        window = script_body[start:end]
        has_get = bool(_GET_METHOD.search(window))
        has_post = bool(_POST_METHOD.search(window))
        if has_post:
            post_near_route = True
        if has_get and not has_post:
            candidate = {"path": shape["path"], "query_keys": shape["query_keys"]}
            if candidate not in strict_get_routes:
                strict_get_routes.append(candidate)

    if strict_get_routes:
        classification = "explicit_script_get_search_route"
    elif route_shapes:
        classification = "search_route_literal_without_strict_get_binding"
    else:
        classification = "no_explicit_search_route_literal"

    return {
        "classification": classification,
        "search_route_shapes": route_shapes,
        "strict_get_search_route_shapes": strict_get_routes,
        "post_method_observed_near_search_route": post_near_route,
        "get_method_token_count": len(_GET_METHOD.findall(script_body)),
        "post_method_token_count": len(_POST_METHOD.findall(script_body)),
        "body_bytes": len(script_body.encode("utf-8", errors="replace")),
    }


def _eligible_cases(layer_payload: dict[str, Any], surface_payload: dict[str, Any]) -> list[dict[str, Any]]:
    surface_by_key = {
        str(item.get("company_key")): item
        for item in surface_payload.get("results", [])
        if item.get("company_key")
    }
    return [
        item
        for item in layer_payload.get("results", [])
        if item.get("first_failure_layer") == "inventory"
        and (surface_by_key.get(str(item.get("company_key"))) or {}).get("authorized_provider")
        == "successfactors"
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only SuccessFactors search-carrier audit for inventory residuals with an "
            "already-authorized SuccessFactors provider surface."
        )
    )
    parser.add_argument("--layer-audit", required=True)
    parser.add_argument("--surface-audit", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    layer_payload = json.loads(Path(args.layer_audit).read_text(encoding="utf-8"))
    surface_payload = json.loads(Path(args.surface_audit).read_text(encoding="utf-8"))
    cases = _eligible_cases(layer_payload, surface_payload)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "job-application-pipeline-successfactors-search-carrier-audit/0.1 (+bounded read-only)",
            "Accept": "text/html,application/xhtml+xml,application/javascript,text/javascript,*/*;q=0.5",
        }
    )

    results: list[dict[str, object]] = []
    request_count = 0
    for item in cases:
        origin = _origin_from_layer(item)
        result: dict[str, object] = {
            "candidate_id": item.get("candidate_id"),
            "company_key": item.get("company_key"),
            "company_name": item.get("company_name"),
        }
        if not origin:
            result["classification"] = "origin_shape_not_replayable"
            results.append(result)
            continue

        try:
            root_response = session.get(origin, timeout=args.timeout_seconds, allow_redirects=True)
            request_count += 1
            root_body = root_response.content
            if len(root_body) > MAX_BODY_BYTES:
                raise RuntimeError("root response body cap exceeded")
            root_html = root_body.decode(root_response.encoding or "utf-8", errors="replace")
            root_url = str(root_response.url)
            result.update(
                {
                    "origin": _safe_url_shape(root_url),
                    "root_status": int(root_response.status_code),
                    "root_get_search_forms": list(explicit_root_get_search_forms(root_url, root_html)),
                }
            )

            scripts = explicit_same_host_search_scripts(root_url, root_html)
            result["explicit_same_host_search_script_count"] = len(scripts)
            result["search_script_shapes"] = [_safe_url_shape(value) for value in scripts]
            if len(scripts) != 1:
                result["classification"] = (
                    "no_unique_explicit_same_host_search_script"
                    if not scripts
                    else "ambiguous_explicit_same_host_search_scripts"
                )
                results.append(result)
                continue

            script_response = session.get(scripts[0], timeout=args.timeout_seconds, allow_redirects=True)
            request_count += 1
            script_body_bytes = script_response.content
            if len(script_body_bytes) > MAX_BODY_BYTES:
                raise RuntimeError("search script body cap exceeded")
            if not _same_https_host(root_url, str(script_response.url)):
                result["classification"] = "search_script_redirected_off_authorized_host"
                results.append(result)
                continue
            script_body = script_body_bytes.decode(script_response.encoding or "utf-8", errors="replace")
            script_evidence = classify_search_script(script_body)
            result["search_script_status"] = int(script_response.status_code)
            result["search_script_final"] = _safe_url_shape(str(script_response.url))
            result["script_evidence"] = script_evidence
            if result["root_get_search_forms"]:
                result["classification"] = "explicit_root_get_search_form"
            else:
                result["classification"] = str(script_evidence["classification"])
        except (requests.RequestException, RuntimeError) as exc:
            result["classification"] = "carrier_fetch_failed"
            result["exception"] = f"{type(exc).__name__}: {exc}"[:500]
        results.append(result)

    counts = Counter(str(item.get("classification") or "<missing>") for item in results)
    output = {
        "schema": SCHEMA,
        "boundary": {
            "eligible_successfactors_inventory_residuals": len(cases),
            "http_get_requests": request_count,
            "max_gets_per_candidate": 2,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "database_reads": 0,
            "database_writes": 0,
            "connector_materialization": 0,
            "query_values_persisted": 0,
        },
        "summary": {"classification_counts": dict(sorted(counts.items()))},
        "results": results,
    }
    Path(args.output).write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("SUCCESSFACTORS SEARCH-CARRIER AUDIT")
    print("============================================")
    print(f"eligible_count={len(cases)}")
    print("classification_counts=" + json.dumps(dict(sorted(counts.items())), sort_keys=True))
    print()
    for item in results:
        print(f"{str(item.get('candidate_id')):>3} | {item.get('company_key')} | {item.get('company_name')}")
        print(f"  classification={item.get('classification')}")
        print(f"  root_get_search_forms={len(item.get('root_get_search_forms', []))}")
        print(f"  same_host_search_scripts={item.get('explicit_same_host_search_script_count', 0)}")
        script_evidence = item.get("script_evidence") or {}
        if isinstance(script_evidence, dict):
            print(
                "  script=" + str(script_evidence.get("classification"))
                + " routes=" + str(script_evidence.get("search_route_shapes"))
                + " strict_get=" + str(script_evidence.get("strict_get_search_route_shapes"))
                + " post_near=" + str(script_evidence.get("post_method_observed_near_search_route"))
            )
    print()
    print(f"HTTP_GET_REQUESTS={request_count}")
    print("PROVIDER_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print("QUERY_VALUES_PERSISTED=0")
    print(f"artifact={args.output}")
    print("SUCCESSFACTORS_SEARCH_CARRIER_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
