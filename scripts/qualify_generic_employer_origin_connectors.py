from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.registry import SourceRole, create_connector, source_role


def _proof_layer(item: dict[str, Any]) -> dict[str, Any] | None:
    layers = item.get("layers") or []
    return next(
        (
            layer
            for layer in layers
            if isinstance(layer, dict) and layer.get("layer") == "proof"
        ),
        None,
    )


def _origin_layer(item: dict[str, Any]) -> dict[str, Any] | None:
    layers = item.get("layers") or []
    return next(
        (
            layer
            for layer in layers
            if isinstance(layer, dict) and layer.get("layer") == "origin"
        ),
        None,
    )


def _load_proof_sources(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    authority = payload.get("authority") or {}
    if authority.get("sole_connector_truth") != "generic_evidence_driven_layer_model":
        raise ValueError("qualification input is not the canonical generic layer product")
    if authority.get("source_validity_gate") != "proof=PASS":
        raise ValueError("qualification input does not use proof=PASS")

    sources: dict[str, dict[str, Any]] = {}
    for item in payload.get("results", []):
        if not isinstance(item, dict):
            continue
        proof = _proof_layer(item)
        if proof is None or proof.get("state") != "pass":
            continue
        company_key = str(item.get("company_key") or "")
        if company_key:
            sources[company_key] = item
    return sources


def _preactivation_materialization_pending(item: dict[str, Any], exc: Exception) -> bool:
    if not isinstance(exc, ValueError) or "no materialized origin URL" not in str(exc):
        return False
    origin = _origin_layer(item)
    if origin is None or origin.get("state") != "pass":
        return False
    evidence = origin.get("evidence") or {}
    return (
        isinstance(evidence, dict)
        and evidence.get("source") == "provider_free_origin_discovery"
    )


def _record_failure(source_name: str, record: object) -> str | None:
    if not isinstance(record, RawJobRecord):
        return "connector emitted non-RawJobRecord"
    if record.source_name != source_name:
        return f"record source mismatch: {record.source_name}"
    admission = record.raw_data.get("bronze_admission")
    if not isinstance(admission, dict) or admission.get("status") != "pass":
        return "emitted record bypassed Bronze admission"
    if admission.get("source_validity_is_separate") is not True:
        return "Bronze admission conflates source and job validity"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Execute every generic layer proof-PASS source through the normal "
            "product registry. Source validity comes from proof=PASS; zero current "
            "Bronze-ready jobs is allowed. Every emitted job must already have "
            "passed the separate Bronze admission gate."
        )
    )
    parser.add_argument("--proof-json", type=Path, required=True)
    args = parser.parse_args()

    proof_sources = _load_proof_sources(args.proof_json)
    keys = list(proof_sources)
    if not keys:
        raise RuntimeError("proof-PASS cohort is empty")

    failures: list[str] = []
    total_records = 0
    zero_bronze_ready = 0
    delivering_sources = 0
    materialization_pending = 0
    for index, company_key in enumerate(keys, start=1):
        source_name = f"generic_origin:{company_key}"
        try:
            if source_role(source_name) != SourceRole.EMPLOYER_ORIGIN:
                failures.append(f"{company_key}: source role is not employer_origin")
                continue

            connector = create_connector(source_name)
            profile = SearchProfile(
                id=0,
                profile_name=f"qualify_{company_key}",
                source_name=source_name,
                search_location="Hannover",
                search_radius_km=50,
                offer_type=1,
                page_size=1,
            )
            records, final_url = connector.fetch_jobs(
                profile,
                SearchTerm("*", id=None),
            )
        except Exception as exc:
            if _preactivation_materialization_pending(proof_sources[company_key], exc):
                zero_bronze_ready += 1
                materialization_pending += 1
                print(
                    f"GENERIC_CONNECTOR={index}/{len(keys)}|{company_key}|"
                    "records=0|final_url=PREACTIVATION_MATERIALIZATION_PENDING"
                )
                print(
                    f"GENERIC_SOURCE_MATERIALIZATION_PENDING={company_key}|"
                    "reason=proof_discovered_origin_not_yet_projected"
                )
                continue
            failures.append(
                f"{company_key}: {type(exc).__name__}: {exc}"
            )
            continue

        total_records += len(records)
        if records:
            delivering_sources += 1
        else:
            zero_bronze_ready += 1
        print(
            f"GENERIC_CONNECTOR={index}/{len(keys)}|{company_key}|"
            f"records={len(records)}|final_url={final_url}"
        )
        for record in records:
            failure = _record_failure(source_name, record)
            if failure:
                failures.append(f"{company_key}: {failure}")
                continue
            print(
                "GENERIC_JOB="
                f"{company_key}|{record.external_job_id}|{record.source_url}|"
                f"{record.raw_data.get('acquisition_evidence', {}).get('proof_kind')}|"
                "bronze_admission=pass"
            )

    print(f"GENERIC_PROOF_COHORT={len(keys)}")
    print(f"GENERIC_DELIVERING_SOURCES={delivering_sources}")
    print(f"GENERIC_ZERO_BRONZE_READY_SOURCES={zero_bronze_ready}")
    print(f"GENERIC_PREACTIVATION_MATERIALIZATION_PENDING={materialization_pending}")
    print(f"GENERIC_BRONZE_READY_RECORDS={total_records}")
    print(f"GENERIC_CONNECTOR_FAILURES={len(failures)}")
    for failure in failures:
        print(f"GENERIC_CONNECTOR_FAILURE={failure}")
    print("DATABASE_WRITES=0")

    if failures:
        raise RuntimeError(
            "proof-PASS sources failed generic product connector execution: "
            + "; ".join(failures)
        )
    print("GENERIC_CONNECTOR_QUALIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
