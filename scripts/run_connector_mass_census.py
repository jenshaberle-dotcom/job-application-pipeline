"""Build a deterministic mass-company census from JSON/NDJSON/CSV seed files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.search_intelligence.connector_mass_census import build_mass_census, seeds_from_payload


def load(path: Path, source: str):
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return seeds_from_payload(list(csv.DictReader(handle)), default_source=source)
    if suffix in {".ndjson", ".jsonl"}:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return seeds_from_payload(rows, default_source=source)
    return seeds_from_payload(json.loads(path.read_text(encoding="utf-8")), default_source=source)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, action="append", required=True)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--region", default="Region Hannover")
    parser.add_argument("--experiment-id", default="hannover-tech-mass-census-v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sources = args.source or []
    seeds = []
    for index, path in enumerate(args.seed):
        source = sources[index] if index < len(sources) else path.stem
        seeds.extend(load(path, source))
    result = build_mass_census(seeds, region=args.region, experiment_id=args.experiment_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["summary"], sort_keys=True))
    print(f"population_digest={result['population_digest']}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
