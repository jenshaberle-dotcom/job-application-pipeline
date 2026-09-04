#!/usr/bin/env python3
"""Bounded read-only probe for an employer-authorized B-ITE postings surface.

The probe performs exactly one POST to the observed B-ITE postings-search endpoint,
keeps the raw response in memory, and emits only compact structural/match evidence.
It never writes Product state or uses a known external vacancy URL as an input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

API_ENDPOINT = "https://jobs.b-ite.com/api/v1/postings/search"
DEFAULT_CLIENT_HEADER = "v5-20260624-f577606"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_INTERESTING_KEY_FRAGMENTS = (
    "id",
    "title",
    "name",
    "company",
    "employer",
    "location",
    "city",
    "place",
    "url",
    "begin",
    "end",
    "date",
)


def build_payload(
    *,
    key: str,
    channel: int,
    locale: str,
    origin: str,
    page_offset: int,
    page_num: int,
    sort_by: str,
    sort_order: str,
    filter_key: str,
    filter_values: list[str],
) -> dict[str, Any]:
    return {
        "key": key,
        "channel": channel,
        "locale": locale,
        "sort": {"by": sort_by, "order": sort_order},
        "origin": origin,
        "page": {"offset": page_offset, "num": page_num},
        "filter": {filter_key: {"in": filter_values}},
    }


def _validate_origin(origin: str) -> None:
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("origin must be an absolute https URL")


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or parsed.hostname != "jobs.b-ite.com":
        raise ValueError("endpoint must be https://jobs.b-ite.com/... for this provider probe")
    if parsed.path != "/api/v1/postings/search":
        raise ValueError("unexpected B-ITE postings-search endpoint path")


def _post_once(
    *, endpoint: str, payload: dict[str, Any], client_header: str, timeout_seconds: float
) -> tuple[int, str, Any]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json;charset=utf-8",
            "Bite-JobsApi-Client": client_header,
            "User-Agent": "JAP-E2E-BITE-READONLY/1",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - endpoint is validated
        status = int(response.status)
        final_url = response.geturl()
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"response exceeded bounded limit of {MAX_RESPONSE_BYTES} bytes")
    if status < 200 or status >= 300:
        raise RuntimeError(f"B-ITE returned HTTP {status}")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("B-ITE response was not valid UTF-8 JSON") from exc
    return status, final_url, document


def _walk(value: Any, path: str = "$", depth: int = 0) -> Iterable[tuple[str, Any]]:
    if depth > 12:
        return
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}", depth + 1)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]", depth + 1)


def find_candidate_containers(document: Any) -> list[tuple[str, int]]:
    preferred = {"jobpostings", "postings", "jobs", "items", "results"}
    found: list[tuple[str, int]] = []
    for path, value in _walk(document):
        if not isinstance(value, list) or not value:
            continue
        leaf = re.split(r"[.\[]", path)[-1].rstrip("]").casefold()
        if leaf in preferred or all(isinstance(item, dict) for item in value[:5]):
            found.append((path, len(value)))
    return found[:20]


def _scalar_pairs(value: Any, path: str = "", depth: int = 0) -> list[tuple[str, str]]:
    if depth > 6:
        return []
    pairs: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            pairs.extend(_scalar_pairs(child, child_path, depth + 1))
    elif isinstance(value, list):
        for index, child in enumerate(value[:30]):
            child_path = f"{path}[{index}]"
            pairs.extend(_scalar_pairs(child, child_path, depth + 1))
    elif value is not None:
        pairs.append((path, str(value)))
    return pairs


def find_matching_objects(document: Any, match_terms: list[str]) -> list[tuple[str, dict[str, Any]]]:
    normalized_terms = [term.casefold().strip() for term in match_terms if term.strip()]
    matches: list[tuple[str, dict[str, Any]]] = []
    for path, value in _walk(document):
        if not isinstance(value, dict):
            continue
        scalar_pairs = _scalar_pairs(value)
        haystack = "\n".join(text.casefold() for _, text in scalar_pairs)
        if normalized_terms and all(term in haystack for term in normalized_terms):
            matches.append((path, value))
    # A matching posting is often nested inside one or more matching wrapper dicts.
    # Keep only the deepest paths so output stays compact and vacancy-oriented.
    deepest: list[tuple[str, dict[str, Any]]] = []
    for candidate in sorted(matches, key=lambda item: item[0].count(".") + item[0].count("["), reverse=True):
        path = candidate[0]
        if any(existing_path.startswith(path + ".") or existing_path.startswith(path + "[") for existing_path, _ in deepest):
            continue
        deepest.append(candidate)
    return list(reversed(deepest[:10]))


def _evidence_fields(value: dict[str, Any]) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    for path, text in _scalar_pairs(value):
        leaf = re.split(r"[.\[]", path)[-1].rstrip("]").casefold()
        is_url = text.startswith("https://") or text.startswith("http://")
        if is_url or any(fragment in leaf for fragment in _INTERESTING_KEY_FRAGMENTS):
            output.append((path, text))
    return output[:40]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--origin", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--filter-key", required=True)
    parser.add_argument("--filter-value", action="append", required=True)
    parser.add_argument("--match-term", action="append", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--endpoint", default=API_ENDPOINT)
    parser.add_argument("--client-header", default=DEFAULT_CLIENT_HEADER)
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--locale", default="de")
    parser.add_argument("--page-offset", type=int, default=0)
    parser.add_argument("--page-num", type=int, default=1000)
    parser.add_argument("--sort-by", default="endsOn")
    parser.add_argument("--sort-order", default="desc")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        _validate_origin(args.origin)
        _validate_endpoint(args.endpoint)
        if not re.fullmatch(r"[0-9a-fA-F]{32,128}", args.key):
            raise ValueError("key must be a bounded hexadecimal public client key")
        if not 1 <= args.page_num <= 1000:
            raise ValueError("page-num must be between 1 and 1000")
        if args.page_offset < 0:
            raise ValueError("page-offset must be non-negative")
        if not args.filter_key or len(args.filter_key) > 128:
            raise ValueError("filter-key is invalid")
        if not args.filter_value or any(not value or len(value) > 128 for value in args.filter_value):
            raise ValueError("filter-value is invalid")

        payload = build_payload(
            key=args.key,
            channel=args.channel,
            locale=args.locale,
            origin=args.origin,
            page_offset=args.page_offset,
            page_num=args.page_num,
            sort_by=args.sort_by,
            sort_order=args.sort_order,
            filter_key=args.filter_key,
            filter_values=args.filter_value,
        )

        print("JAP_DEVELOPMENT_NAVIGATOR")
        print("CAMPAIGN=E2E-SLICE-001")
        print(f"SUBJECT={args.subject}")
        print("MOVEMENT=VERTICAL_SPIKE")
        print("HORIZONTAL_POSITION=Employer-Origin -> current exact vacancy")
        print("VERTICAL_CAPABILITY=B-ITE provider / tenant vacancy acquisition")
        print("RETURN_CONDITION=current employer-origin vacancy proven -> resume at Bronze")
        print(f"BITE_ENDPOINT={args.endpoint}")
        print("JOB_API_POST_BUDGET=1")
        print("KNOWN_EXTERNAL_VACANCY_URL_SEEDED=NO")

        status, final_url, document = _post_once(
            endpoint=args.endpoint,
            payload=payload,
            client_header=args.client_header,
            timeout_seconds=args.timeout_seconds,
        )
        print(f"HTTP_STATUS={status}")
        print(f"HTTP_FINAL_URL={final_url}")
        print(f"RESPONSE_TOP_LEVEL={type(document).__name__}")
        if isinstance(document, dict):
            print("RESPONSE_TOP_KEYS=" + ",".join(sorted(str(key) for key in document.keys())[:80]))

        containers = find_candidate_containers(document)
        print(f"CANDIDATE_CONTAINER_COUNT={len(containers)}")
        for index, (path, count) in enumerate(containers, start=1):
            print(f"CONTAINER[{index}].path={path}")
            print(f"CONTAINER[{index}].count={count}")

        matches = find_matching_objects(document, args.match_term)
        print(f"MATCH_COUNT={len(matches)}")
        for index, (path, value) in enumerate(matches, start=1):
            print(f"MATCH[{index}].path={path}")
            print("MATCH[%d].keys=%s" % (index, ",".join(sorted(str(key) for key in value.keys())[:80])))
            for field_path, text in _evidence_fields(value):
                compact = " ".join(text.split())
                if len(compact) > 600:
                    compact = compact[:597] + "..."
                print(f"MATCH[{index}].field.{field_path}={compact}")

        print("PRODUCT_DB_MUTATION=NONE")
        print("PRODUCT_STATE_MUTATION=NONE")
        print("RAW_RESPONSE_PERSISTED=NO")
        if not matches:
            print("BITE_EMPLOYER_ORIGIN_PROBE=NO_MATCH")
            return 4
        print("BITE_EMPLOYER_ORIGIN_PROBE=PASS")
        return 0
    except Exception as exc:  # compact diagnostic boundary; no retry
        print(f"BITE_EMPLOYER_ORIGIN_PROBE=FAIL type={type(exc).__name__} detail={exc}")
        print("PRODUCT_DB_MUTATION=NONE")
        print("PRODUCT_STATE_MUTATION=NONE")
        return 2


if __name__ == "__main__":
    sys.exit(main())
