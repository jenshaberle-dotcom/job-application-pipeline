from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.connectors.successfactors import (
    MAX_DETAIL_PAGES_HARD_LIMIT,
    SuccessFactorsConnector,
)
from src.connectors.successfactors_preview import SuccessFactorsPreviewConnector


def record_summary(record: RawJobRecord) -> dict[str, object]:
    result_card = record.raw_data.get("result_card", {})
    job = record.raw_data.get("job", {})
    detail_evidence = record.raw_data.get("detail_evidence", {})
    listing_evidence = record.raw_data.get("listing_evidence", {})
    description = str(job.get("description") or "")
    return {
        "external_job_id": record.external_job_id,
        "title": result_card.get("title"),
        "company_name": result_card.get("company_name"),
        "location": result_card.get("location"),
        "source_url": record.source_url,
        "matched_profile_terms": listing_evidence.get("matched_profile_terms", []),
        "target_employer_verified": detail_evidence.get(
            "target_employer_verified",
            False,
        ),
        "description_excerpt": description[:500],
    }


def build_preview_payload(
    *,
    connector: SuccessFactorsConnector,
    records: list[RawJobRecord],
    final_url: str,
    search_term: str,
) -> dict[str, object]:
    return {
        "artifact_type": "successfactors_connector_preview",
        "schema_version": "1.0",
        "target_key": connector.target.target_key,
        "source_name": connector.source_name,
        "listing_url": final_url,
        "search_term": search_term,
        "record_count": len(records),
        "records": [record_summary(record) for record in records],
        "provider_requests": 0,
        "pipeline_mutation": False,
        "source_activation_allowed": False,
        "review_output_only_not_pipeline_input": True,
        "boundary": {
            "listing_pages": 1,
            "pagination_enabled": False,
            "max_detail_pages": connector.max_detail_pages,
            "max_http_requests": 1 + connector.max_detail_pages,
            "browser_automation_used": False,
            "access_control_bypass_used": False,
            "database_write": False,
            "bronze_write": False,
            "silver_write": False,
            "scheduler_change": False,
        },
    }


def write_output(path: Path, payload: dict[str, object]) -> None:
    if path.exists():
        raise ValueError(f"output path already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded read-only SuccessFactors connector preview."
    )
    parser.add_argument("--target-key", default="eon_germany")
    parser.add_argument("--search-term", default="*")
    parser.add_argument(
        "--max-detail-pages",
        type=int,
        default=MAX_DETAIL_PAGES_HARD_LIMIT,
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    connector = SuccessFactorsPreviewConnector(
        target_key=args.target_key,
        max_detail_pages=args.max_detail_pages,
    )
    profile = SearchProfile(
        id=-1,
        profile_name="successfactors_review_preview",
        source_name=connector.source_name,
        search_location=None,
        search_radius_km=None,
        offer_type=None,
        page_size=connector.max_detail_pages,
    )
    records, final_url = connector.fetch_jobs(
        profile,
        SearchTerm(search_term=args.search_term, id=None),
    )
    payload = build_preview_payload(
        connector=connector,
        records=records,
        final_url=final_url,
        search_term=args.search_term,
    )

    if args.output:
        write_output(args.output, payload)
        print(f"artifact_json: {args.output}")

    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
