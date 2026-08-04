"""Run a two-stage, evidence-reusing origin URL audit.

The ordinary database audit is intentionally fresh and therefore repeats every
provider search. This runner is for bounded regression and acceptance work when
provider credits are scarce:

1. read the selected company inventory and close the DB transaction;
2. run deterministic baseline plus symbol/operator evidence for every company;
3. treat selected URLs from earlier audit artifacts only as *untrusted hints*;
4. revalidate every hint with the current DNS, identity, origin-type and HTTP gates;
5. spend Tavily/LLM budget only for companies still unresolved after phase A.

No prior result is copied into pipeline truth. No database state is mutated.
"""

from __future__ import annotations

import argparse
from collections import Counter
from copy import copy
from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Mapping, Sequence
from urllib.parse import urlparse

from scripts import run_origin_url_database_audit as legacy
from scripts.run_origin_source_discovery_agent import load_local_env_file
from scripts.run_origin_url_default_repair import run_default_repair_for_company
from src.search_intelligence.origin_quality_contract import (
    canonical_origin_from_job_detail,
)

SCHEMA_VERSION = "origin_url_budgeted_database_audit.v1"
Runner = Callable[[argparse.Namespace, str], dict[str, object]]


def _selected(payload: Mapping[str, object] | None) -> bool:
    if not isinstance(payload, Mapping):
        return False
    repair = payload.get("default_repair")
    if not isinstance(repair, Mapping):
        return False
    return str(repair.get("final_state") or "").startswith("selected_") and bool(
        repair.get("selected_url")
    )


def _https_url(value: object) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return raw


def seed_urls_from_selected_url(value: object) -> tuple[str, ...]:
    """Return conservative portal and original URL hints in validation order."""

    url = _https_url(value)
    if url is None:
        return ()
    candidates: list[str] = []
    portal = canonical_origin_from_job_detail(url)
    if portal:
        candidates.append(portal)
    if url not in candidates:
        candidates.append(url)
    return tuple(candidates)


def load_seed_hints(paths: Sequence[Path]) -> tuple[dict[str, tuple[str, ...]], list[dict[str, object]]]:
    """Load untrusted selected URLs from prior read-only audit artifacts.

    The artifacts must explicitly declare their review-only and non-mutating
    boundary. URLs are never accepted as truth; they are only returned as hints
    for the current deterministic validation contract.
    """

    collected: dict[str, list[str]] = {}
    provenance: list[dict[str, object]] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("review_output_only_not_pipeline_input") is not True:
            raise ValueError(f"seed artifact is not review-only: {path}")
        if data.get("database_write") is not False:
            raise ValueError(f"seed artifact does not prove database_write=false: {path}")
        rows = data.get("companies")
        if not isinstance(rows, list):
            raise ValueError(f"seed artifact has no companies array: {path}")
        accepted_rows = 0
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            company_key = str(row.get("company_key") or "").strip()
            if not company_key:
                continue
            hints = seed_urls_from_selected_url(row.get("selected_url"))
            if not hints:
                continue
            bucket = collected.setdefault(company_key, [])
            for hint in hints:
                if hint not in bucket:
                    bucket.append(hint)
            accepted_rows += 1
        provenance.append(
            {
                "path": str(path),
                "schema_version": data.get("schema_version"),
                "generated_at_utc": data.get("generated_at_utc"),
                "selected_rows_used_as_untrusted_hints": accepted_rows,
            }
        )
    return {key: tuple(values) for key, values in collected.items()}, provenance


def _repair_args(
    args: argparse.Namespace,
    *,
    operator_urls: Sequence[str],
    deterministic_only: bool,
) -> SimpleNamespace:
    base = legacy.repair_args(args)
    repair = copy(base)
    repair.operator_url = list(operator_urls)
    if deterministic_only:
        repair.disable_tavily = True
        repair.disable_llm = True
    return repair


def run_company_phases(
    args: argparse.Namespace,
    *,
    company_key: str,
    operator_urls: Sequence[str],
    runner: Runner = run_default_repair_for_company,
) -> tuple[dict[str, object], dict[str, object] | None, str]:
    """Run deterministic phase A and optional provider phase B for one company."""

    phase_a = runner(
        _repair_args(args, operator_urls=operator_urls, deterministic_only=True),
        company_key,
    )
    if _selected(phase_a):
        return phase_a, None, "phase_a_deterministic"
    if args.phase == "deterministic":
        return phase_a, None, "phase_a_unresolved"
    phase_b = runner(
        _repair_args(args, operator_urls=operator_urls, deterministic_only=False),
        company_key,
    )
    return phase_b, phase_a, "phase_b_provider"


def _row(
    company: Mapping[str, object],
    payload: Mapping[str, object] | None,
    *,
    audit_phase: str,
    seed_urls: Sequence[str],
    phase_a_payload: Mapping[str, object] | None = None,
    error: str | None = None,
    budget_blocked: bool = False,
) -> dict[str, object]:
    row = legacy.result_row(
        company,
        payload,
        error=error,
        budget_blocked=budget_blocked,
    )
    if audit_phase == "phase_a_unresolved" and not error:
        row["final_state"] = "deterministic_unresolved"
        row["configuration_blocked"] = False
    row["audit_phase"] = audit_phase
    row["seed_url_count"] = len(seed_urls)
    row["seed_urls"] = list(seed_urls)
    if isinstance(phase_a_payload, Mapping):
        repair = phase_a_payload.get("default_repair")
        repair_map = repair if isinstance(repair, Mapping) else {}
        row["phase_a_final_state"] = repair_map.get("final_state")
        row["phase_a_selected_url"] = repair_map.get("selected_url")
    else:
        row["phase_a_final_state"] = row.get("final_state")
        row["phase_a_selected_url"] = row.get("selected_url")
    return row


def run(args: argparse.Namespace) -> dict[str, object]:
    maximum = args.max_companies if args.max_companies > 0 else None
    with legacy.connect() as conn:
        companies = legacy.load_current_companies(
            conn,
            statuses=tuple(args.status),
            company_keys=tuple(args.company_key),
            maximum=maximum,
        )
        conn.rollback()

    seed_hints, seed_provenance = load_seed_hints(tuple(args.seed_audit_artifact))
    rows: list[dict[str, object]] = []
    final_payloads: list[dict[str, object]] = []
    phase_a_payloads: list[dict[str, object]] = []
    provider_total = 0
    web_search_total = 0
    llm_total = 0

    for index, company in enumerate(companies, start=1):
        key = str(company.get("company_key") or "")
        hints = seed_hints.get(key, ())
        if args.phase == "two-stage" and (
            provider_total >= args.max_provider_requests
            or llm_total >= args.max_llm_requests
        ):
            # Phase A is free of Tavily/LLM and is still useful. Execute it, then
            # surface an explicit phase-B budget guard when it remains unresolved.
            try:
                phase_a = run_default_repair_for_company(
                    _repair_args(args, operator_urls=hints, deterministic_only=True),
                    key,
                )
            except Exception as exc:  # noqa: BLE001 - per-company isolation
                message = f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}"
                rows.append(
                    _row(
                        company,
                        None,
                        audit_phase="phase_a_error",
                        seed_urls=hints,
                        error=message,
                    )
                )
                continue
            if _selected(phase_a):
                payload = phase_a
                prior_phase = None
                audit_phase = "phase_a_deterministic"
            else:
                rows.append(
                    _row(
                        company,
                        None,
                        audit_phase="phase_b_budget_guard",
                        seed_urls=hints,
                        phase_a_payload=phase_a,
                        budget_blocked=True,
                    )
                )
                phase_a_payloads.append(phase_a)
                print(
                    f"origin_budgeted_audit: {index}/{len(companies)} company_key={key} "
                    "final_state=not_run_budget_guard phase=phase_b_provider"
                )
                continue
        else:
            try:
                payload, prior_phase, audit_phase = run_company_phases(
                    args,
                    company_key=key,
                    operator_urls=hints,
                )
            except Exception as exc:  # noqa: BLE001 - per-company isolation
                message = f"{type(exc).__name__}: {' '.join(str(exc).split())[:500]}"
                rows.append(
                    _row(
                        company,
                        None,
                        audit_phase="error",
                        seed_urls=hints,
                        error=message,
                    )
                )
                print(
                    f"origin_budgeted_audit: {index}/{len(companies)} company_key={key} "
                    f"final_state=error error={message}"
                )
                if args.stop_on_error:
                    raise
                continue

        row = _row(
            company,
            payload,
            audit_phase=audit_phase,
            seed_urls=hints,
            phase_a_payload=prior_phase,
        )
        accounting = legacy.request_accounting(payload)
        provider_total += accounting["external_provider_requests"]
        web_search_total += accounting["web_search_requests"]
        llm_total += accounting["llm_requests"]
        rows.append(row)
        final_payloads.append(payload)
        if isinstance(prior_phase, Mapping):
            phase_a_payloads.append(dict(prior_phase))
        print(
            f"origin_budgeted_audit: {index}/{len(companies)} company_key={key} "
            f"phase={audit_phase} final_state={row['final_state']} "
            f"selected_url={row['selected_url'] or '<none>'} "
            f"seed_urls={len(hints)} provider_requests={row['provider_requests']} "
            f"web_search_requests={row['web_search_requests']} "
            f"llm_requests={row['llm_requests']}"
        )

    final_counts = Counter(str(row.get("final_state") or "error") for row in rows)
    phase_counts = Counter(str(row.get("audit_phase") or "unknown") for row in rows)
    selected_count = sum(
        1 for row in rows if str(row.get("final_state") or "").startswith("selected_")
    )
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "review_output_only_not_pipeline_input": True,
        "database_write": False,
        "all_companies_requested": args.all_companies,
        "mode": args.phase,
        "seed_contract": {
            "prior_selected_urls_are_truth": False,
            "prior_selected_urls_are_untrusted_operator_hints": True,
            "current_runtime_revalidation_required": True,
            "artifacts": seed_provenance,
        },
        "filters": {
            "statuses": list(args.status),
            "company_keys": list(args.company_key),
            "max_companies": maximum,
        },
        "request_accounting": {
            "provider_requests": "all external Tavily and OpenAI requests",
            "web_search_requests": "Tavily requests only",
            "llm_requests": "actual OpenAI requests only",
        },
        "budget": {
            "max_provider_requests": args.max_provider_requests,
            "max_llm_requests": args.max_llm_requests,
            "provider_requests_used": provider_total,
            "web_search_requests_used": web_search_total,
            "llm_requests_used": llm_total,
        },
        "summary": {
            "company_count": len(companies),
            "executed_count": len(final_payloads),
            "selected_count": selected_count,
            "operator_review_count": final_counts.get("operator_review_required", 0),
            "configuration_blocked_count": final_counts.get(
                "repair_configuration_blocked", 0
            ),
            "repair_exhausted_count": final_counts.get("repair_exhausted", 0),
            "deterministic_unresolved_count": final_counts.get(
                "deterministic_unresolved", 0
            ),
            "error_count": sum(1 for row in rows if row.get("error")),
            "budget_guard_count": final_counts.get("not_run_budget_guard", 0),
            "provider_request_count": provider_total,
            "web_search_request_count": web_search_total,
            "llm_request_count": llm_total,
            "seeded_company_count": sum(1 for row in rows if row.get("seed_url_count")),
            "final_state_counts": dict(sorted(final_counts.items())),
            "audit_phase_counts": dict(sorted(phase_counts.items())),
            "selected_stage_counts": dict(
                sorted(
                    Counter(
                        str(row.get("selected_stage"))
                        for row in rows
                        if row.get("selected_stage")
                    ).items()
                )
            ),
        },
        "companies": rows,
        "repair_payloads": final_payloads,
        "phase_a_payloads": phase_a_payloads,
    }
    json_path, md_path, csv_path = legacy.write_outputs(report, args.output_dir)
    print(f"artifact_json: {json_path}")
    print(f"artifact_markdown: {md_path}")
    print(f"artifact_csv: {csv_path}")
    print("RESULT: ORIGIN_URL_BUDGETED_AUDIT_COMPLETED")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = legacy.build_parser()
    parser.description = (
        "Run deterministic-first origin audit and spend provider budget only on "
        "unresolved companies."
    )
    parser.add_argument(
        "--phase",
        choices=("deterministic", "two-stage"),
        default="two-stage",
        help="Stop after free deterministic validation or continue unresolved firms.",
    )
    parser.add_argument(
        "--seed-audit-artifact",
        action="append",
        type=Path,
        default=[],
        help=(
            "Prior read-only audit JSON. Selected URLs become untrusted hints and "
            "must pass the current deterministic gates. Repeatable."
        ),
    )
    return parser


def main() -> None:
    load_local_env_file()
    args = build_parser().parse_args()
    if args.max_companies < 0:
        raise SystemExit("--max-companies must not be negative")
    if args.max_provider_requests < 0 or args.max_llm_requests < 0:
        raise SystemExit("request ceilings must not be negative")
    for path in args.seed_audit_artifact:
        if not path.is_file():
            raise SystemExit(f"seed audit artifact does not exist: {path}")
    run(args)


if __name__ == "__main__":
    main()
