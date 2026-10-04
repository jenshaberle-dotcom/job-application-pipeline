from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.connectors.factory_aggressive_policy import FactoryCandidate, evaluate_population


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate every admitted employer candidate through the aggressive generic-first Connector Factory.")
    parser.add_argument("--census", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--catalog", default="contracts/connector-capability-catalog-v1.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    census = json.loads(Path(args.census).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    catalog = json.loads(Path(args.catalog).read_text(encoding="utf-8"))
    evidence_by_key = {str(row["company_key"]): row for row in evidence.get("sources", [])}

    candidates = []
    for row in census["candidates"]:
        source = evidence_by_key.get(str(row["company_key"]), {})
        candidates.append(
            FactoryCandidate(
                company_key=str(row["company_key"]),
                company_name=str(row["company_name"]),
                cohort=str(row.get("cohort", "TECH")),
                origin_url=source.get("origin_url"),
                source_type=source.get("source_type"),
                fingerprint_tags=tuple(source.get("fingerprint_tags", [])),
                evidence_ids=tuple(source.get("evidence_ids", row.get("discovery_evidence_ids", []))),
                origin_verified=source.get("origin_verified") is True,
            )
        )

    result = evaluate_population(candidates, catalog)
    result["input_population_digest"] = census["population_digest"]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_count": result["candidate_count"], "disposition_counts": result["disposition_counts"], "engineering_groups": len(result["engineering_queue"]), "output": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
