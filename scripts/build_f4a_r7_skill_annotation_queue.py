"""Build a deterministic manual-review queue for R7 skill candidate contexts.

The queue is research-only. It combines the broad Gazetteer Shadow seed with the
learned-context Shadow seed to prioritize diverse manual review, while keeping
all labels empty. Observer agreement is selection metadata only and never
becomes training truth or Product authority.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


SEED_SCHEMA = "job_application_pipeline.f4a_r7_skill_annotation_seed.v1"
QUEUE_SCHEMA = "job_application_pipeline.f4a_r7_skill_annotation_queue.v1"


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


def _normalized(value: object) -> str:
    return _text(value).casefold()


def _validate_seed(seed: Mapping[str, Any], *, name: str) -> list[Mapping[str, Any]]:
    if seed.get("schema") != SEED_SCHEMA:
        raise ValueError(f"unsupported {name} annotation seed schema")
    if seed.get("mode") != "annotation_seed_only":
        raise ValueError(f"{name} seed is not annotation-only")
    boundaries = _mapping(seed.get("boundaries"))
    if any(bool(value) for value in boundaries.values()):
        raise ValueError(f"{name} seed violates annotation boundaries")
    records = seed.get("records")
    if not isinstance(records, list):
        raise ValueError(f"{name} seed has no records list")
    return [_mapping(record) for record in records]


def _candidate_span(text: str, candidate: str) -> tuple[int, int, str]:
    start = text.find(candidate)
    if start >= 0:
        end = start + len(candidate)
        return start, end, text[start:end]

    parts = candidate.split()
    if not parts:
        raise ValueError("annotation candidate is empty")
    pattern = re.compile(r"\s+".join(re.escape(part) for part in parts))
    match = pattern.search(text)
    if match is None:
        raise ValueError(f"annotation candidate is not grounded in requirement text: {candidate!r}")
    return match.start(), match.end(), text[match.start() : match.end()]


def _context_window(
    text: str,
    *,
    start: int,
    end: int,
    token_radius: int,
) -> tuple[int, int, str]:
    tokens = list(re.finditer(r"\S+", text))
    if not tokens:
        return 0, len(text), text

    hit_indexes = [
        index
        for index, token in enumerate(tokens)
        if token.end() > start and token.start() < end
    ]
    if not hit_indexes:
        raise ValueError("grounded annotation span has no token overlap")
    first = max(0, hit_indexes[0] - token_radius)
    last = min(len(tokens) - 1, hit_indexes[-1] + token_radius)
    context_start = tokens[first].start()
    context_end = tokens[last].end()
    return context_start, context_end, text[context_start:context_end]


def _annotation_id(*, record_id: str, start: int, end: int, evidence: str) -> str:
    payload = f"{record_id}\0{start}\0{end}\0{evidence}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def _stable_round_robin(
    rows: Sequence[dict[str, object]], *, limit: int
) -> list[dict[str, object]]:
    strata: dict[tuple[str, bool, bool], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row["split_group"]),
            bool(row["skill_recall_risk"]),
            bool(row["learned_proxy_positive"]),
        )
        strata[key].append(row)
    for bucket in strata.values():
        bucket.sort(key=lambda row: str(row["annotation_id"]))

    selected: list[dict[str, object]] = []
    keys = sorted(strata)
    while len(selected) < limit:
        progressed = False
        for key in keys:
            bucket = strata[key]
            if not bucket:
                continue
            selected.append(bucket.pop(0))
            progressed = True
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return selected


def build_annotation_queue(
    gazetteer_seed: Mapping[str, Any],
    learned_seed: Mapping[str, Any],
    *,
    limit: int = 400,
    context_tokens: int = 20,
) -> dict[str, object]:
    if limit <= 0:
        raise ValueError("annotation queue limit must be positive")
    if context_tokens <= 0:
        raise ValueError("annotation context token radius must be positive")

    gazetteer_records = _validate_seed(gazetteer_seed, name="gazetteer")
    learned_records = _validate_seed(learned_seed, name="learned")
    learned_by_id = {
        _text(record.get("record_id")): record for record in learned_records
    }

    candidates: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for record in gazetteer_records:
        record_id = _text(record.get("record_id"))
        if not record_id:
            raise ValueError("gazetteer seed record has no record_id")
        learned = learned_by_id.get(record_id)
        if learned is None:
            raise ValueError(f"learned seed is missing record {record_id}")
        if record.get("requirement_text_sha256") != learned.get("requirement_text_sha256"):
            raise ValueError(f"annotation seed text drift for record {record_id}")
        if record.get("split_group") != learned.get("split_group"):
            raise ValueError(f"annotation seed split-group drift for record {record_id}")

        requirement_text = str(record.get("requirement_text") or "")
        if not requirement_text:
            continue
        learned_candidates = {
            _normalized(value) for value in _string_list(learned.get("shadow_candidates"))
        }
        for candidate in _string_list(record.get("shadow_candidates")):
            start, end, evidence = _candidate_span(requirement_text, candidate)
            annotation_id = _annotation_id(
                record_id=record_id,
                start=start,
                end=end,
                evidence=evidence,
            )
            if annotation_id in seen_ids:
                continue
            seen_ids.add(annotation_id)
            context_start, context_end, context = _context_window(
                requirement_text,
                start=start,
                end=end,
                token_radius=context_tokens,
            )
            candidates.append(
                {
                    "schema": QUEUE_SCHEMA,
                    "annotation_id": annotation_id,
                    "seed_record_id": record_id,
                    "silver_job_id": int(record["silver_job_id"]),
                    "source_name": _text(record.get("source_name")) or "unknown",
                    "source_host": _text(record.get("source_host")) or "unknown",
                    "split_group": _text(record.get("split_group")) or "unknown",
                    "title": _text(record.get("title")),
                    "requirement_text_sha256": str(record["requirement_text_sha256"]),
                    "candidate": candidate,
                    "evidence": evidence,
                    "span_start": start,
                    "span_end": end,
                    "context_start": context_start,
                    "context_end": context_end,
                    "context": context,
                    "context_token_radius": context_tokens,
                    "skill_recall_risk": record.get("skill_recall_risk") is True,
                    "gazetteer_shadow_candidate": True,
                    "learned_proxy_positive": _normalized(candidate) in learned_candidates,
                    "annotation_status": "unreviewed",
                    "gold_label": None,
                    "gold_subtype": None,
                    "annotator_notes": "",
                }
            )

    selected = _stable_round_robin(candidates, limit=min(limit, len(candidates)))
    for index, row in enumerate(selected, start=1):
        row["selection_rank"] = index

    split_groups: dict[str, int] = {}
    for row in selected:
        group = str(row["split_group"])
        split_groups[group] = split_groups.get(group, 0) + 1

    return {
        "schema": QUEUE_SCHEMA,
        "mode": "manual_annotation_queue_only",
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "selection_limit": limit,
        "context_token_radius": context_tokens,
        "split_group_count": len(split_groups),
        "split_groups": dict(sorted(split_groups.items())),
        "learned_proxy_positive_count": sum(
            bool(row["learned_proxy_positive"]) for row in selected
        ),
        "gazetteer_only_count": sum(
            not bool(row["learned_proxy_positive"]) for row in selected
        ),
        "recall_risk_context_count": sum(
            bool(row["skill_recall_risk"]) for row in selected
        ),
        "records": selected,
        "boundaries": {
            "database_writes": 0,
            "silver_writes": 0,
            "product_authority": 0,
            "labels_invented": 0,
            "observer_proxy_as_gold": 0,
            "raw_html_persisted": 0,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("gazetteer_seed", type=Path)
    parser.add_argument("learned_seed", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=400)
    parser.add_argument("--context-tokens", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    gazetteer_seed = json.loads(args.gazetteer_seed.read_text(encoding="utf-8"))
    learned_seed = json.loads(args.learned_seed.read_text(encoding="utf-8"))
    if not isinstance(gazetteer_seed, Mapping) or not isinstance(learned_seed, Mapping):
        raise SystemExit("R7 annotation seeds must be JSON objects")
    queue = build_annotation_queue(
        gazetteer_seed,
        learned_seed,
        limit=args.limit,
        context_tokens=args.context_tokens,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(f"F4A_R7_ANNOTATION_QUEUE_CANDIDATES={queue['candidate_count']}")
    print(f"F4A_R7_ANNOTATION_QUEUE_SELECTED={queue['selected_count']}")
    print(f"F4A_R7_ANNOTATION_QUEUE_GROUPS={queue['split_group_count']}")
    print(
        "F4A_R7_ANNOTATION_QUEUE_GROUP_COUNTS="
        + json.dumps(queue["split_groups"], ensure_ascii=False, sort_keys=True)
    )
    print(
        "F4A_R7_ANNOTATION_QUEUE_PROXY_POSITIVE="
        + str(queue["learned_proxy_positive_count"])
    )
    print("F4A_R7_ANNOTATION_QUEUE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
