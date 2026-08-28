from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.origin_source_discovery_agent import (
    acronym_tokens,
    company_identity_tokens,
    corporate_identity_aliases,
    generate_company_url_candidates,
)

SCHEMA = "job_application_pipeline.deterministic_origin_plan_audit.v1"
DEFAULT_BUDGET = 12
DEFAULT_EXPANDED_BUDGET = 500


def connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def load_candidates(conn: psycopg.Connection[Any], company_keys: set[str]) -> dict[str, dict[str, Any]]:
    if not company_keys:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (company_key)
                id,
                company_key,
                company_name,
                candidate_url,
                source_family_candidate,
                status,
                risk_level,
                updated_at
            FROM employer_origin_source_candidates
            WHERE company_key = ANY(%s)
            ORDER BY company_key, updated_at DESC NULLS LAST, id DESC
            """,
            (sorted(company_keys),),
        )
        return {str(row["company_key"]): dict(row) for row in cur.fetchall()}


def normalized_host(url: str) -> str:
    return (urlparse(url).hostname or "").casefold().removeprefix("www.")


def corporate_host_family(url: str) -> str:
    host = normalized_host(url)
    for prefix in ("jobs.", "careers.", "career.", "karriere."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
            break
    return host


def compact_company_key(company_key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", company_key.casefold())


def label_before_tld(host: str) -> str:
    parts = [part for part in host.split(".") if part]
    if len(parts) < 2:
        return parts[0] if parts else ""
    return parts[-2]


def first_position_matching(candidates: tuple[object, ...], labels: set[str]) -> int | None:
    if not labels:
        return None
    for index, candidate in enumerate(candidates, start=1):
        label = label_before_tld(corporate_host_family(str(candidate.url)))
        if label in labels:
            return index
    return None


def audit_row(row: dict[str, Any], *, budget: int, expanded_budget: int) -> dict[str, object]:
    company_key = str(row["company_key"])
    company_name = str(row["company_name"])
    source_family = str(row.get("source_family_candidate") or "")

    identity = company_identity_tokens(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family,
    )
    acronyms = acronym_tokens(company_name)
    aliases = corporate_identity_aliases(company_key, company_name)

    bounded = generate_company_url_candidates(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family,
        max_candidates=budget,
    )
    expanded = generate_company_url_candidates(
        company_key=company_key,
        company_name=company_name,
        source_family_candidate=source_family,
        max_candidates=expanded_budget,
    )

    bounded_families = [corporate_host_family(item.url) for item in bounded]
    expanded_families = [corporate_host_family(item.url) for item in expanded]
    bounded_unique = tuple(dict.fromkeys(bounded_families))
    expanded_unique = tuple(dict.fromkeys(expanded_families))

    acronym_labels = {token.casefold() for token in acronyms if token}
    compact_label = compact_company_key(company_key)
    compact_labels = {compact_label} if compact_label else set()

    acronym_position = first_position_matching(expanded, acronym_labels)
    compact_position = first_position_matching(expanded, compact_labels)

    generated_total = len(expanded)
    budget_saturated = len(bounded) >= budget and generated_total > budget
    domain_family_monoculture = len(bounded_unique) <= 1 and budget_saturated
    acronym_delayed = bool(acronym_position and acronym_position > budget)
    compact_key_delayed = bool(compact_position and compact_position > budget)

    reasons: list[str] = []
    if domain_family_monoculture:
        reasons.append("bounded plan is consumed by one corporate host family")
    if acronym_delayed:
        reasons.append("acronym/short-brand host hypothesis exists only after the active budget")
    if compact_key_delayed:
        reasons.append("compact company-key host hypothesis exists only after the active budget")
    if acronyms and all(token in identity for token in acronyms):
        reasons.append("acronym is already an identity token and is therefore not promoted as a separate generic base")
    if not aliases:
        reasons.append("no explicit corporate identity alias is available")
    if not reasons:
        reasons.append("no obvious plan-geometry bottleneck detected; probe/scoring or missing hypothesis class requires follow-up")

    return {
        "candidate_id": int(row["id"]),
        "company_key": company_key,
        "company_name": company_name,
        "identity_tokens": list(identity),
        "acronym_tokens": list(acronyms),
        "corporate_aliases": list(aliases),
        "active_budget": budget,
        "expanded_budget": expanded_budget,
        "bounded_candidate_count": len(bounded),
        "expanded_candidate_count": generated_total,
        "bounded_unique_host_family_count": len(bounded_unique),
        "expanded_unique_host_family_count": len(expanded_unique),
        "bounded_host_families": list(bounded_unique),
        "expanded_host_families_preview": list(expanded_unique[:20]),
        "acronym_first_position": acronym_position,
        "compact_key_first_position": compact_position,
        "budget_saturated": budget_saturated,
        "domain_family_monoculture": domain_family_monoculture,
        "acronym_delayed_beyond_budget": acronym_delayed,
        "compact_key_delayed_beyond_budget": compact_key_delayed,
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit provider-free origin candidate-plan geometry for candidates that failed the origin layer."
    )
    parser.add_argument("--layer-audit", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--expanded-budget", type=int, default=DEFAULT_EXPANDED_BUDGET)
    args = parser.parse_args()

    if args.budget < 1 or args.expanded_budget < args.budget:
        raise SystemExit("invalid budget configuration")

    layer_payload = json.loads(Path(args.layer_audit).read_text(encoding="utf-8"))
    origin_failures = [
        item
        for item in layer_payload.get("results", [])
        if item.get("first_failure_layer") == "origin"
    ]
    company_keys = {str(item["company_key"]) for item in origin_failures}

    with connect() as conn:
        rows = load_candidates(conn, company_keys)

    missing = sorted(company_keys - set(rows))
    if missing:
        raise SystemExit(f"candidate rows missing for company keys: {missing}")

    results = [
        audit_row(rows[key], budget=args.budget, expanded_budget=args.expanded_budget)
        for key in sorted(company_keys)
    ]

    classifications = Counter()
    for item in results:
        if item["domain_family_monoculture"]:
            classifications["domain_family_monoculture"] += 1
        if item["acronym_delayed_beyond_budget"]:
            classifications["acronym_delayed_beyond_budget"] += 1
        if item["compact_key_delayed_beyond_budget"]:
            classifications["compact_key_delayed_beyond_budget"] += 1
        if not item["corporate_aliases"]:
            classifications["no_corporate_alias"] += 1

    payload = {
        "schema": SCHEMA,
        "boundary": {
            "database_reads": True,
            "database_writes": False,
            "http_requests": 0,
            "provider_requests": 0,
            "llm_requests": 0,
            "tavily_requests": 0,
            "connector_materialization": 0,
        },
        "summary": {
            "origin_failure_count": len(results),
            "active_budget": args.budget,
            "expanded_budget": args.expanded_budget,
            "classification_counts": dict(sorted(classifications.items())),
        },
        "results": results,
    }

    Path(args.output).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("============================================")
    print("DETERMINISTIC ORIGIN PLAN AUDIT")
    print("============================================")
    print(f"origin_failure_count={len(results)}")
    print("classification_counts=" + json.dumps(dict(sorted(classifications.items())), sort_keys=True))
    print()
    for item in results:
        print(f"{item['candidate_id']:>3} | {item['company_key']} | {item['company_name']}")
        print(
            "  bounded="
            f"{item['bounded_candidate_count']} candidates / "
            f"{item['bounded_unique_host_family_count']} host families; "
            f"expanded={item['expanded_candidate_count']} / "
            f"{item['expanded_unique_host_family_count']}"
        )
        print(
            "  acronym_pos="
            f"{item['acronym_first_position']} "
            f"compact_key_pos={item['compact_key_first_position']}"
        )
        print("  bounded_hosts=" + ", ".join(item["bounded_host_families"][:8]))
        for reason in item["reasons"]:
            print(f"  - {reason}")
    print()
    print("HTTP_REQUESTS=0")
    print("PROVIDER_REQUESTS=0")
    print("DATABASE_WRITES=0")
    print(f"artifact={args.output}")
    print("ORIGIN_PLAN_AUDIT=COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
