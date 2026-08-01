"""Run deterministic employer-origin inventory resolution from a JSON input."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Mapping

from src.search_intelligence.origin_inventory_resolution import (
    ExternalJobSignal,
    candidate_from_mapping,
    resolve_origin_inventory,
)


def _mapping(value: object, *, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SystemExit(f"{field} must be an object")
    return value


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve observed origin inventories without mutation or provider calls."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    root = _mapping(payload, field="input")

    raw_candidates = root.get("candidates")
    if not isinstance(raw_candidates, list):
        raise SystemExit("candidates must be a list")
    candidates = tuple(
        candidate_from_mapping(_mapping(item, field="candidate"))
        for item in raw_candidates
    )

    raw_external_signal = _mapping(
        root.get("external_job_signal"),
        field="external_job_signal",
    )
    signal = ExternalJobSignal(
        currently_live=raw_external_signal.get("currently_live"),
        confidence=float(raw_external_signal.get("confidence", 0.0)),
        observation_count=int(raw_external_signal.get("observation_count", 1)),
        origin_miss_count=int(raw_external_signal.get("origin_miss_count", 0)),
    )

    as_of_raw = str(root.get("as_of") or "").strip()
    if not as_of_raw:
        raise SystemExit("as_of is required in YYYY-MM-DD format")

    result = resolve_origin_inventory(
        company_key=str(root["company_key"]),
        company_name=str(root["company_name"]),
        candidates=candidates,
        external_job_signal=signal,
        as_of=date.fromisoformat(as_of_raw),
        failed_reobservation_attempt=int(root.get("failed_reobservation_attempt", 0)),
        new_external_job_event=bool(root.get("new_external_job_event", False)),
    )
    output = result.to_json()
    _write_json(args.output, output)
    print(
        "origin_inventory_resolution_complete: "
        f"company={result.company_key} status={result.status} "
        f"families={len(result.source_families)} output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
