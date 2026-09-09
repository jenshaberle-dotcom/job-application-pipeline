from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.connectors.base import SearchProfile, SearchTerm
from src.connectors.registry import create_connector, source_role, SourceRole


def _load_proof_keys(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    authority = payload.get("authority") or {}
    if authority.get("sole_connector_truth") != "generic_evidence_driven_layer_model":
        raise ValueError("qualification input is not the canonical generic layer product")
    if authority.get("source_validity_gate") != "proof=PASS":
        raise ValueError("qualification input does not use proof=PASS")
    return [str(value) for value in payload.get("proof_pass_company_keys", [])]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Require every generic layer proof-PASS source to emit at least one "
            "RawJobRecord through the normal product registry interface."
        )
    )
    parser.add_argument("--proof-json", type=Path, required=True)
    args = parser.parse_args()

    keys = _load_proof_keys(args.proof_json)
    if not keys:
        raise RuntimeError("proof-PASS cohort is empty")

    failures: list[str] = []
    total_records = 0
    for index, company_key in enumerate(keys, start=1):
        source_name = f"generic_origin:{company_key}"
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
            SearchTerm("jobs", id=None),
        )
        total_records += len(records)
        print(
            f"GENERIC_CONNECTOR={index}/{len(keys)}|{company_key}|"
            f"records={len(records)}|final_url={final_url}"
        )
        for record in records:
            print(
                "GENERIC_JOB="
                f"{company_key}|{record.external_job_id}|{record.source_url}|"
                f"{record.raw_data.get('acquisition_evidence', {}).get('proof_kind')}"
            )
        if not records:
            failures.append(f"{company_key}: zero records through generic registry")

    print(f"GENERIC_PROOF_COHORT={len(keys)}")
    print(f"GENERIC_CONNECTOR_RECORDS={total_records}")
    print(f"GENERIC_CONNECTOR_FAILURES={len(failures)}")
    for failure in failures:
        print(f"GENERIC_CONNECTOR_FAILURE={failure}")
    print("DATABASE_WRITES=0")

    if failures:
        raise RuntimeError(
            "proof-PASS sources failed generic product connector qualification: "
            + "; ".join(failures)
        )
    print("GENERIC_CONNECTOR_QUALIFICATION=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
