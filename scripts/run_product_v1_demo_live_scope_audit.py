from __future__ import annotations

import json

from scripts.run_product_v1_control_center import load_product_v1_payload
from src.search_intelligence.product_v1_demo_live_scope import (
    project_demo_live_scope,
)


def main() -> int:
    payload = load_product_v1_payload()
    jobs = payload.get("job_readiness") or []
    projected = project_demo_live_scope(
        [item for item in jobs if isinstance(item, dict)]
    )
    live = [item for item in projected if item.get("demo_live_verified")]
    rankable = [
        item
        for item in live
        if str(item.get("product_readiness_status") or "") == "rankable"
    ]
    print(
        json.dumps(
            {
                "status": "demo_live_scope_audit",
                "job_count": len(projected),
                "demo_live_verified": len(live),
                "demo_live_rankable": len(rankable),
                "rows": [
                    {
                        "silver_job_id": item.get("silver_job_id"),
                        "title": item.get("title"),
                        "company_name": item.get("company_name"),
                        "product_readiness_status": item.get("product_readiness_status"),
                        "demo_actionable": item.get("demo_actionable"),
                        "demo_actionability_reason": item.get("demo_actionability_reason"),
                        "demo_live_verified": item.get("demo_live_verified"),
                        "demo_live_reason": item.get("demo_live_reason"),
                        "employer_origin_url": item.get("employer_origin_url"),
                    }
                    for item in projected
                ],
                "boundary": {
                    "database_writes": 0,
                    "network_requests": 0,
                    "provider_requests": 0,
                    "ranking_authority": False,
                },
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
