from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any


SCHEMA = "job_application_pipeline.deterministic_detail_identifier_reclassification.v1"

HIGH_CONFIDENCE_IDENTIFIER_SUFFIXES = (
    "objectid",
    "jobid",
    "requisitionid",
    "reqid",
    "vacancyid",
    "positionid",
    "postingid",
    "openingid",
)

CLASSIFICATION_PRIORITY = (
    "strict_query_detail_already_visible",
    "unknown_query_identifier_key_surface",
    "form_driven_detail_surface",
    "unclassified_jobish_detail_surface",
    "client_rendered_or_script_detail_surface",
    "provider_detail_route_gap",
    "low_signal_detail_surface",
)


def _normalized_query_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def high_confidence_unknown_identifier_key(value: str) -> bool:
    """Return true only for unknown keys with explicit job/detail ID semantics.

    The earlier surface audit intentionally used a broad diagnostic heuristic. Live
    evidence showed that substring matching on plain ``id`` admits tracking keys
    such as ``icid`` / ``igshid`` / ``linkid`` and even incidental word fragments.
    This offline layer therefore requires a semantic identifier suffix instead of
    treating any occurrence of ``id`` as detail identity evidence.
    """

    normalized = _normalized_query_key(value)
    return bool(
        normalized
        and any(normalized.endswith(suffix) for suffix in HIGH_CONFIDENCE_IDENTIFIER_SUFFIXES)
    )


def reclassify_page(page: dict[str, Any]) -> dict[str, Any]:
    original_unknown = {
        str(key): int(count)
        for key, count in (page.get("unknown_identifier_query_keys") or {}).items()
    }
    retained_unknown = {
        key: count
        for key, count in original_unknown.items()
        if high_confidence_unknown_identifier_key(key)
    }
    suppressed_unknown = {
        key: count
        for key, count in original_unknown.items()
        if key not in retained_unknown
    }

    if int(page.get("trusted_query_detail_count") or 0) > 0:
        classification = "strict_query_detail_already_visible"
    elif retained_unknown:
        classification = "unknown_query_identifier_key_surface"
    elif bool(page.get("form_detail_signal")):
        classification = "form_driven_detail_surface"
    elif int(page.get("unclassified_jobish_anchor_count") or 0) > 0:
        classification = "unclassified_jobish_detail_surface"
    elif page.get("client_markers") or page.get("script_job_markers"):
        classification = "client_rendered_or_script_detail_surface"
    elif page.get("provider_hints"):
        classification = "provider_detail_route_gap"
    else:
        classification = "low_signal_detail_surface"

    result = dict(page)
    result["original_classification"] = page.get("classification")
    result["classification"] = classification
    result["unknown_identifier_query_keys"] = dict(sorted(retained_unknown.items()))
    result["suppressed_unknown_identifier_query_keys"] = dict(sorted(suppressed_unknown.items()))
    return result


def _primary_classification(page_summaries: list[dict[str, Any]]) -> str:
    observed = {str(page.get("classification") or "") for page in page_summaries}
    return next(
        (classification for classification in CLASSIFICATION_PRIORITY if classification in observed),
        "low_signal_detail_surface",
    )


def reclassify_case(item: dict[str, Any]) -> dict[str, Any]:
    pages = [reclassify_page(dict(page)) for page in item.get("page_summaries", [])]
    if bool(item.get("current_v4_now_resolves_detail")):
        classification = "current_v4_now_resolves_detail"
    elif str(item.get("classification") or "") == "origin_shape_not_replayable":
        classification = "origin_shape_not_replayable"
    else:
        classification = _primary_classification(pages)

    result = dict(item)
    result["original_classification"] = item.get("classification")
    result["classification"] = classification
    result["page_summaries"] = pages
    return result


def reclassify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    results = [reclassify_case(dict(item)) for item in payload.get("results", [])]

    before = Counter(str(item.get("classification") or "") for item in payload.get("results", []))
    after = Counter(str(item.get("classification") or "") for item in results)
    changed = [
        str(item.get("company_key") or "")
        for item in results
        if item.get("classification") != item.get("original_classification")
    ]

    retained_keys: defaultdict[str, Counter[str]] = defaultdict(Counter)
    suppressed_keys: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for item in results:
        company = str(item.get("company_key") or "")
        for page in item.get("page_summaries", []):
            for key, count in (page.get("unknown_identifier_query_keys") or {}).items():
                retained_keys[company][str(key)] += int(count)
            for key, count in (page.get("suppressed_unknown_identifier_query_keys") or {}).items():
                suppressed_keys[company][str(key)] += int(count)

    return {
        "schema": SCHEMA,
        "source_schema": payload.get("schema"),
        "boundary": {
            "network_requests": 0,
            "database_reads": 0,
            "database_writes": 0,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "connector_materialization": 0,
            "query_values_read": 0,
            "query_values_persisted": 0,
            "input_case_count": len(results),
        },
        "summary": {
            "classification_counts_before": dict(sorted(before.items())),
            "classification_counts_after": dict(sorted(after.items())),
            "changed_candidate_count": len(changed),
            "changed_company_keys": sorted(changed),
            "retained_identifier_company_count": sum(1 for values in retained_keys.values() if values),
            "suppressed_identifier_company_count": sum(1 for values in suppressed_keys.values() if values),
        },
        "retained_identifier_keys": {
            company: dict(sorted(values.items()))
            for company, values in sorted(retained_keys.items())
            if values
        },
        "suppressed_identifier_keys": {
            company: dict(sorted(values.items()))
            for company, values in sorted(suppressed_keys.items())
            if values
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Offline reclassification of detail residual identifier evidence using "
            "semantic query-key suffixes; performs no network or database access."
        )
    )
    parser.add_argument("--detail-audit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = json.loads(Path(args.detail_audit).read_text(encoding="utf-8"))
    output = reclassify_payload(source)
    Path(args.output).write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("DETAIL IDENTIFIER RECLASSIFICATION")
    print("============================================")
    print("before=" + json.dumps(output["summary"]["classification_counts_before"], sort_keys=True))
    print("after=" + json.dumps(output["summary"]["classification_counts_after"], sort_keys=True))
    print("changed=" + json.dumps(output["summary"]["changed_company_keys"], sort_keys=True))
    print("retained_identifier_keys=" + json.dumps(output["retained_identifier_keys"], sort_keys=True))
    print("suppressed_identifier_keys=" + json.dumps(output["suppressed_identifier_keys"], sort_keys=True))
    print("NETWORK_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print("QUERY_VALUES_PERSISTED=0")
    print(f"artifact={args.output}")
    print("DETAIL_IDENTIFIER_RECLASSIFICATION=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
