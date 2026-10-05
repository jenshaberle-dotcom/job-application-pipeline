"""Run configured sources independently; preserve failures and usable partial populations."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from scripts.build_connector_ml_corpus import build
from src.search_intelligence.discovery_coverage import assess
from src.search_intelligence.public_directory_discovery import discovery_failure

CONFIGS = (
    "contracts/discovery/berlin-startup-map.json",
    "contracts/discovery/wolfsburg-innovations.json",
    "contracts/discovery/ingolstadt-digital.json",
)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run(output_dir: Path, *, execute=subprocess.run, source_timeout: int = 240) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    providers = [
        (
            "hochschule_hannover_career_center",
            "REGION_HANNOVER",
            "scripts.discover_hannover_tech_hsh",
            [],
        ),
        ("munich_startup", "MUNICH", "scripts.discover_munich_startups", []),
        (
            "region_stuttgart_technology_directory",
            "STUTTGART_REGION",
            "scripts.discover_stuttgart_tech",
            [],
        ),
    ]
    for config_path in CONFIGS:
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        providers.append(
            (
                config["source_id"],
                config["geography"],
                "scripts.discover_configured_directory",
                ["--config", config_path],
            )
        )
    snapshots = []
    outcomes = []
    for source, geography, module, options in providers:
        target = output_dir / (source + ".json")
        # Never include a prior successful file after this attempt fails.
        target.unlink(missing_ok=True)
        outcome = {"source_id": source, "geography": geography, "company_count": 0}
        try:
            execute(
                [sys.executable, "-m", module, *options, "--output", str(target)],
                check=True,
                timeout=source_timeout,
                capture_output=True,
                text=True,
            )
            payload = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(payload.get("companies"), list):
                raise ValueError("source_companies_list_required")
            outcome.update(
                status="SUCCESS" if payload["companies"] else "NO_RECORDS_PARSED",
                company_count=len(payload["companies"]),
                snapshot_digest=hashlib.sha256(target.read_bytes()).hexdigest(),
            )
            if not payload["companies"]:
                outcome["empty_result_semantics"] = "NOT_MARKET_ABSENCE"
            # Propagate an adapter's explicit incompleteness; a successful
            # subprocess is not evidence that pagination was exhausted.
            if payload.get("complete") is False:
                outcome["complete"] = False
            snapshots.append(str(target))
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            outcome.update(
                status="SOURCE_DISCOVERY_FAILURE",
                failure_type=type(exc).__name__,
                **discovery_failure(exc),
            )
            target.unlink(missing_ok=True)
        outcomes.append(outcome)
    census_path = output_dir / "multi-region-company-census.json"
    if snapshots and any(row["company_count"] for row in outcomes):
        census = build(snapshots)
        write_json(census_path, census)
        coverage = assess(census)
        coverage.update(population_digest=census["population_digest"], sources=outcomes)
    else:
        census_path.unlink(missing_ok=True)
        coverage = assess({"candidates": []})
        coverage.update(sources=outcomes)
    write_json(output_dir / "discovery-coverage.json", coverage)
    if not census_path.exists():
        raise RuntimeError("no_usable_company_population: see discovery-coverage.json")
    return census_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="artifacts/connector-corpus")
    args = parser.parse_args()
    census = run(Path(args.output_dir))
    print(json.dumps({"census": str(census)}, sort_keys=True))


if __name__ == "__main__":
    main()
