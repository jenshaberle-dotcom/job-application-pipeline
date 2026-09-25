"""Freeze-II S1A all-candidate connector saturation smoke.

This is a connector-contract proof, not source/Product proof. Every current
Employer-Origin candidate must resolve through the canonical generic connector
family and emit exactly one synthetic RawJobRecord through the shared connector
contract. Synthetic records use the reserved .invalid domain, are never
persisted, and never enter Bronze/Silver/Product.

The same report also records whether a current materialized real origin URL
exists, which is the hand-off into S1B/S1C real-source execution.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts import run_deterministic_connector_builder_layer_audit as candidate_core
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.employer_origin_acquisition import AcquiredJobPage
from src.connectors.generic_employer_origin import (
    GenericEmployerOriginConnector,
    GenericOriginSource,
)
from src.connectors.registry import SourceRole, create_connector, source_role


SCHEMA = "job_application_pipeline.freeze2_connector_saturation_smoke.v1"
SMOKE_TERM = "__freeze2_connector_contract_smoke__"
SMOKE_HOST = "connector-smoke.invalid"


def _synthetic_source(row: dict[str, Any]) -> GenericOriginSource:
    return GenericOriginSource(
        candidate_id=int(row["id"]),
        company_key=str(row["company_key"]),
        company_name=str(row["company_name"]),
        candidate_url=f"https://{SMOKE_HOST}/{row['company_key']}",
    )


def _synthetic_job(source: GenericOriginSource) -> AcquiredJobPage:
    url = f"{source.candidate_url}/jobs/smoke-job"
    return AcquiredJobPage(
        requested_url=url,
        final_url=url,
        status_code=200,
        title="Connector Contract Smoke Job",
        html_bytes=128,
        proof_kind="synthetic_contract_smoke_only",
        discovery_source="freeze2_s1a_synthetic_smoke",
        anchor_text="Connector Contract Smoke Job",
    )


def _smoke_candidate(row: dict[str, Any]) -> dict[str, Any]:
    company_key = str(row["company_key"])
    source_name = f"generic_origin:{company_key}"
    result: dict[str, Any] = {
        "candidate_id": int(row["id"]),
        "company_key": company_key,
        "company_name": str(row["company_name"]),
        "source_name": source_name,
        "candidate_status": str(row.get("status") or ""),
        "real_origin_url_present": bool(str(row.get("candidate_url") or "").strip()),
        "registry_binding": False,
        "registry_role": None,
        "connector_class": None,
        "synthetic_record_count": 0,
        "smoke_pass": False,
        "failure": None,
    }

    try:
        role = source_role(source_name)
        result["registry_role"] = str(role)
        if role != SourceRole.EMPLOYER_ORIGIN:
            raise RuntimeError(f"unexpected source role: {role}")

        registry_connector = create_connector(source_name)
        result["connector_class"] = type(registry_connector).__name__
        if not isinstance(registry_connector, GenericEmployerOriginConnector):
            raise RuntimeError(
                "canonical generic_origin binding did not resolve to "
                "GenericEmployerOriginConnector"
            )
        result["registry_binding"] = True

        source = _synthetic_source(row)
        smoke_connector = GenericEmployerOriginConnector(
            company_key=company_key,
            source_name=source_name,
            candidate_loader=lambda requested, source=source: (
                source
                if requested == source.company_key
                else (_raise_bad_key(requested, source.company_key))
            ),
            job_acquirer=_synthetic_job,
        )
        records, final_url = smoke_connector.fetch_jobs(
            SearchProfile(
                id=0,
                profile_name=f"freeze2_smoke_{company_key}",
                source_name=source_name,
                search_location="Hannover",
                search_radius_km=None,
                offer_type=None,
                page_size=1,
            ),
            SearchTerm(search_term=SMOKE_TERM, id=0),
        )
        result["synthetic_record_count"] = len(records)
        if len(records) != 1:
            raise RuntimeError(f"expected one synthetic record, got {len(records)}")
        record = records[0]
        if not isinstance(record, RawJobRecord):
            raise RuntimeError("smoke connector emitted non-RawJobRecord")
        if record.source_name != source_name:
            raise RuntimeError(
                f"source identity mismatch: {record.source_name!r} != {source_name!r}"
            )
        if SMOKE_HOST not in record.source_url or SMOKE_HOST not in final_url:
            raise RuntimeError("synthetic smoke escaped reserved .invalid source")
        if (
            record.raw_data.get("acquisition_evidence", {}).get("proof_kind")
            != "synthetic_contract_smoke_only"
        ):
            raise RuntimeError("synthetic smoke proof marker missing")
        result["smoke_pass"] = True
    except Exception as exc:  # noqa: BLE001 - full denominator must be reported.
        result["failure"] = f"{type(exc).__name__}: {exc}"[:1000]

    return result


def _raise_bad_key(requested: str, expected: str) -> GenericOriginSource:
    raise RuntimeError(
        f"smoke candidate loader key mismatch: requested={requested!r} "
        f"expected={expected!r}"
    )


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    results = [_smoke_candidate(row) for row in rows]
    smoke_pass = sum(1 for row in results if row["smoke_pass"])
    real_origin_present = sum(1 for row in results if row["real_origin_url_present"])
    failures = [row for row in results if not row["smoke_pass"]]
    return {
        "schema": SCHEMA,
        "mode": "isolated_synthetic_connector_contract",
        "authority": {
            "product_source_validity": False,
            "real_job_evidence": False,
            "bronze_authority": False,
            "silver_authority": False,
            "product_authority": False,
            "activation_authority": False,
            "synthetic_record_persistence_allowed": False,
        },
        "summary": {
            "candidate_count": len(results),
            "registry_binding_count": sum(
                1 for row in results if row["registry_binding"]
            ),
            "smoke_pass_count": smoke_pass,
            "smoke_failure_count": len(failures),
            "connector_saturation_ratio": (
                smoke_pass / len(results) if results else 0.0
            ),
            "real_origin_url_present_count": real_origin_present,
            "real_origin_url_missing_count": len(results) - real_origin_present,
        },
        "results": results,
        "next_gate": (
            "S1B/S1C real-source execution across the same complete candidate "
            "denominator; each candidate must resolve to real_jobs_observed, "
            "real_zero_yield, or an explicit source blocker."
        ),
        "boundaries": {
            "database_reads": True,
            "database_writes": 0,
            "network_requests": 0,
            "synthetic_records_persisted": 0,
            "bronze_writes": 0,
            "silver_writes": 0,
            "product_writes": 0,
            "source_activation": 0,
            "connector_registration": 0,
            "provider_requests": 0,
            "llm_requests": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/freeze2-connector-saturation-smoke.json"),
    )
    args = parser.parse_args(argv)

    with candidate_core._connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
            rows = candidate_core._load_candidates(conn)
        conn.rollback()

    report = build_report(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = report["summary"]
    print("============================================")
    print("FREEZE-II S1A CONNECTOR SATURATION SMOKE")
    print("============================================")
    print(f"CANDIDATES={summary['candidate_count']}")
    print(f"REGISTRY_BINDINGS={summary['registry_binding_count']}")
    print(f"SMOKE_PASS={summary['smoke_pass_count']}")
    print(f"SMOKE_FAILURE={summary['smoke_failure_count']}")
    print(f"REAL_ORIGIN_PRESENT={summary['real_origin_url_present_count']}")
    print(f"REAL_ORIGIN_MISSING={summary['real_origin_url_missing_count']}")
    for row in report["results"]:
        state = "PASS" if row["smoke_pass"] else "FAIL"
        print(
            "CONNECTOR_SMOKE="
            f"{row['company_key']}|{state}|"
            f"class={row['connector_class']}|"
            f"origin_present={str(row['real_origin_url_present']).lower()}|"
            f"failure={row['failure'] or '-'}"
        )
    print("NETWORK_REQUESTS=0")
    print("SYNTHETIC_RECORDS_PERSISTED=0")
    print("DATABASE_WRITES=0")
    print(f"artifact={args.output}")

    if summary["candidate_count"] <= 0:
        raise RuntimeError("candidate denominator is empty")
    if summary["smoke_failure_count"]:
        raise RuntimeError(
            f"connector saturation smoke failed for "
            f"{summary['smoke_failure_count']} candidates"
        )
    print("FREEZE2_CONNECTOR_SATURATION_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
