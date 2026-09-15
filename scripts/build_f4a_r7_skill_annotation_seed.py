"""Build an annotation-ready R7 skill-span seed from a read-only audit report.

The builder is deliberately offline and tool-neutral. It consumes a previously
produced R7 audit JSON file and emits bounded employer-origin requirement text
plus provenance/grouping metadata. No labels are invented: deterministic skills
and external Shadow candidates are suggestions only, while ``gold_spans`` starts
empty for human review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SEED_SCHEMA = "job_application_pipeline.f4a_r7_skill_annotation_seed.v1"
AUDIT_SCHEMA = "job_application_pipeline.f4a_r7_skill_reliability_audit.v2"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _text(item)
        if text and text not in result:
            result.append(text)
    return result


def _record_id(*, source_host: str, silver_job_id: int, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{source_host}:{silver_job_id}:{digest}"


def build_seed(report: Mapping[str, Any]) -> dict[str, object]:
    if report.get("schema") != AUDIT_SCHEMA:
        raise ValueError("unsupported R7 audit schema")
    if report.get("mode") != "read_only":
        raise ValueError("annotation seed requires a read-only audit report")

    rows = report.get("rows")
    if not isinstance(rows, list):
        raise ValueError("R7 audit report has no rows list")

    records: list[dict[str, object]] = []
    groups: dict[str, int] = {}
    for raw in rows:
        row = _mapping(raw)
        requirement_text = str(row.get("requirement_section_text") or "").strip()
        if not requirement_text:
            continue
        source_host = _text(row.get("source_host")) or "unknown"
        source_name = _text(row.get("source_name")) or "unknown"
        silver_job_id = int(row["silver_job_id"])
        split_group = source_host
        groups[split_group] = groups.get(split_group, 0) + 1
        records.append(
            {
                "schema": SEED_SCHEMA,
                "record_id": _record_id(
                    source_host=source_host,
                    silver_job_id=silver_job_id,
                    text=requirement_text,
                ),
                "silver_job_id": silver_job_id,
                "source_name": source_name,
                "source_host": source_host,
                "split_group": split_group,
                "title": _text(row.get("title")),
                "requirement_text": requirement_text,
                "requirement_text_sha256": hashlib.sha256(
                    requirement_text.encode("utf-8")
                ).hexdigest(),
                "deterministic_skills": _string_list(row.get("skills")),
                "shadow_candidates": _string_list(
                    row.get("external_incremental_skill_spans")
                ),
                "skill_recall_risk": row.get("skill_recall_risk") is True,
                "annotation_status": "unreviewed",
                "gold_spans": [],
                "negative_spans": [],
            }
        )

    return {
        "schema": SEED_SCHEMA,
        "mode": "annotation_seed_only",
        "record_count": len(records),
        "split_group_count": len(groups),
        "split_groups": dict(sorted(groups.items())),
        "records": records,
        "boundaries": {
            "database_writes": 0,
            "silver_writes": 0,
            "product_authority": 0,
            "labels_invented": 0,
            "raw_html_persisted": 0,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = json.loads(args.audit_report.read_text(encoding="utf-8"))
    if not isinstance(report, Mapping):
        raise SystemExit("R7 audit report must be a JSON object")
    seed = build_seed(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(seed, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"F4A_R7_ANNOTATION_SEED_RECORDS={seed['record_count']}")
    print(f"F4A_R7_ANNOTATION_SEED_GROUPS={seed['split_group_count']}")
    print(
        "F4A_R7_ANNOTATION_SEED_GROUP_COUNTS="
        + json.dumps(seed["split_groups"], ensure_ascii=False, sort_keys=True)
    )
    print("F4A_R7_ANNOTATION_SEED=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
