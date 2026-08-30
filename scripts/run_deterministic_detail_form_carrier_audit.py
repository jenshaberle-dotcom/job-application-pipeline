from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from typing import Any


SCHEMA = "job_application_pipeline.deterministic_detail_form_carrier_audit.v1"

SEMANTIC_IDENTIFIER_SUFFIXES = (
    "objectid",
    "jobid",
    "requisitionid",
    "reqid",
    "vacancyid",
    "positionid",
    "postingid",
    "openingid",
)

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

SEARCH_FILTER_FIELD_MARKERS = (
    "q",
    "query",
    "search",
    "keyword",
    "keywords",
    "location",
    "country",
    "city",
    "category",
    "department",
    "brand",
    "filter",
    "facet",
    "sort",
    "page",
)

FORM_CLASS_PRIORITY = (
    "get_jobish_with_semantic_identifier_field",
    "post_jobish_with_semantic_identifier_field",
    "get_jobish_search_or_filter_form",
    "post_jobish_search_or_filter_form",
    "get_jobish_form_without_semantic_identifier",
    "post_jobish_form_without_semantic_identifier",
    "other_jobish_form",
    "non_jobish_form",
    "no_form_evidence",
)


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _semantic_identifier_field(value: str) -> bool:
    normalized = _normalized(value)
    return bool(
        normalized
        and any(normalized.endswith(suffix) for suffix in SEMANTIC_IDENTIFIER_SUFFIXES)
    )


def _search_filter_field(value: str) -> bool:
    normalized = _normalized(value)
    if not normalized:
        return False
    return any(
        normalized == marker or normalized.startswith(marker) or normalized.endswith(marker)
        for marker in SEARCH_FILTER_FIELD_MARKERS
    )


def _jobish_action(action: dict[str, Any]) -> bool:
    surface = f"{action.get('host', '')}{action.get('path', '')}".casefold()
    return any(marker in surface for marker in JOB_MARKERS)


def _path_pattern(value: str) -> str:
    parts = [part for part in str(value or "/").split("/") if part]
    normalized_parts = [":num" if part.isdigit() else part.casefold() for part in parts]
    return "/" + "/".join(normalized_parts) if normalized_parts else "/"


def classify_form(form: dict[str, Any]) -> dict[str, Any]:
    method = str(form.get("method") or "get").casefold()
    action = dict(form.get("action") or {})
    fields = [str(value) for value in form.get("field_names", [])]

    semantic_fields = sorted({field for field in fields if _semantic_identifier_field(field)})
    search_filter_fields = sorted({field for field in fields if _search_filter_field(field)})
    jobish = _jobish_action(action)

    if jobish and semantic_fields and method == "get":
        classification = "get_jobish_with_semantic_identifier_field"
    elif jobish and semantic_fields and method == "post":
        classification = "post_jobish_with_semantic_identifier_field"
    elif jobish and search_filter_fields and method == "get":
        classification = "get_jobish_search_or_filter_form"
    elif jobish and search_filter_fields and method == "post":
        classification = "post_jobish_search_or_filter_form"
    elif jobish and method == "get":
        classification = "get_jobish_form_without_semantic_identifier"
    elif jobish and method == "post":
        classification = "post_jobish_form_without_semantic_identifier"
    elif jobish:
        classification = "other_jobish_form"
    else:
        classification = "non_jobish_form"

    return {
        "classification": classification,
        "method": method,
        "action": {
            "scheme": str(action.get("scheme") or "").casefold(),
            "host": str(action.get("host") or "").casefold(),
            "path": str(action.get("path") or "/"),
            "path_pattern": _path_pattern(str(action.get("path") or "/")),
            "query_keys": sorted(str(value) for value in action.get("query_keys", [])),
        },
        "field_names": fields,
        "semantic_identifier_fields": semantic_fields,
        "search_filter_fields": search_filter_fields,
        "jobish_action": jobish,
    }


def _primary_form_class(forms: list[dict[str, Any]]) -> str:
    observed = {str(item.get("classification") or "") for item in forms}
    return next((value for value in FORM_CLASS_PRIORITY if value in observed), "no_form_evidence")


def audit_case(item: dict[str, Any]) -> dict[str, Any]:
    forms: list[dict[str, Any]] = []
    provider_hints: set[str] = set()
    pages_with_form_signal = 0

    for page in item.get("page_summaries", []):
        provider_hints.update(str(value) for value in page.get("provider_hints", []))
        if not bool(page.get("form_detail_signal")):
            continue
        pages_with_form_signal += 1
        for form in page.get("forms", []):
            forms.append(classify_form(dict(form)))

    return {
        "company_key": item.get("company_key"),
        "company_name": item.get("company_name"),
        "source_classification": item.get("classification"),
        "classification": _primary_form_class(forms),
        "pages_with_form_signal": pages_with_form_signal,
        "form_count": len(forms),
        "provider_hints": sorted(provider_hints),
        "forms": forms,
    }


def audit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    selected = [
        dict(item)
        for item in payload.get("results", [])
        if item.get("classification") == "form_driven_detail_surface"
    ]
    results = [audit_case(item) for item in selected]

    classification_counts = Counter(str(item["classification"]) for item in results)
    action_pattern_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for item in results:
        company = str(item.get("company_key") or "")
        for form in item.get("forms", []):
            action = form.get("action") or {}
            signature = "|".join(
                [
                    str(form.get("method") or ""),
                    str(action.get("host") or ""),
                    str(action.get("path_pattern") or "/"),
                    str(form.get("classification") or ""),
                ]
            )
            action_pattern_counts[signature][company] += 1

    cross_company_signatures = {
        signature: sorted(companies)
        for signature, counts in sorted(action_pattern_counts.items())
        if len((companies := set(counts))) >= 2
    }

    return {
        "schema": SCHEMA,
        "source_schema": payload.get("schema"),
        "boundary": {
            "input_form_driven_cases": len(selected),
            "network_requests": 0,
            "form_submissions": 0,
            "database_reads": 0,
            "database_writes": 0,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "connector_materialization": 0,
            "query_values_read": 0,
            "query_values_persisted": 0,
            "form_values_read": 0,
            "form_values_persisted": 0,
        },
        "summary": {
            "classification_counts": dict(sorted(classification_counts.items())),
            "cross_company_signature_count": len(cross_company_signatures),
        },
        "cross_company_signatures": cross_company_signatures,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Zero-network structural audit of already-recorded form-driven detail residuals. "
            "Never submits forms or reconstructs form values."
        )
    )
    parser.add_argument("--reclassification", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source = json.loads(Path(args.reclassification).read_text(encoding="utf-8"))
    output = audit_payload(source)
    Path(args.output).write_text(
        json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("DETAIL FORM CARRIER AUDIT")
    print("============================================")
    print(f"form_driven_case_count={output['boundary']['input_form_driven_cases']}")
    print("classification_counts=" + json.dumps(output["summary"]["classification_counts"], sort_keys=True))
    print(f"cross_company_signature_count={output['summary']['cross_company_signature_count']}")
    for item in output["results"]:
        print(f"{item.get('company_key')} | class={item.get('classification')} forms={item.get('form_count')}")
        for form in item.get("forms", []):
            action = form.get("action") or {}
            print(
                "  - method=" + str(form.get("method"))
                + " action=" + str(action.get("host")) + str(action.get("path_pattern"))
                + " class=" + str(form.get("classification"))
                + " semantic_fields=" + json.dumps(form.get("semantic_identifier_fields") or [])
                + " search_fields=" + json.dumps(form.get("search_filter_fields") or [])
            )
    print("NETWORK_REQUESTS=0")
    print("FORM_SUBMISSIONS=0")
    print("FORM_VALUES_READ=0")
    print("DATABASE_WRITES=0")
    print(f"artifact={args.output}")
    print("DETAIL_FORM_CARRIER_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
