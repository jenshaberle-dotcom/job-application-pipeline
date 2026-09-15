from __future__ import annotations

import copy

import pytest

from scripts.build_f4a_r7_skill_annotation_queue import build_annotation_queue


SEED_SCHEMA = "job_application_pipeline.f4a_r7_skill_annotation_seed.v1"


def _record(
    *,
    record_id: str,
    job_id: int,
    host: str,
    text: str,
    candidates: list[str],
    risk: bool,
) -> dict[str, object]:
    return {
        "schema": SEED_SCHEMA,
        "record_id": record_id,
        "silver_job_id": job_id,
        "source_name": f"source:{host}",
        "source_host": host,
        "split_group": host,
        "title": f"Job {job_id}",
        "requirement_text": text,
        "requirement_text_sha256": f"sha-{record_id}",
        "deterministic_skills": [],
        "shadow_candidates": candidates,
        "skill_recall_risk": risk,
        "annotation_status": "unreviewed",
        "gold_spans": [],
        "negative_spans": [],
    }


def _seed(records: list[dict[str, object]]) -> dict[str, object]:
    groups: dict[str, int] = {}
    for record in records:
        group = str(record["split_group"])
        groups[group] = groups.get(group, 0) + 1
    return {
        "schema": SEED_SCHEMA,
        "mode": "annotation_seed_only",
        "record_count": len(records),
        "split_group_count": len(groups),
        "split_groups": groups,
        "records": records,
        "boundaries": {
            "database_writes": 0,
            "silver_writes": 0,
            "product_authority": 0,
            "labels_invented": 0,
            "raw_html_persisted": 0,
        },
    }


def test_queue_preserves_exact_span_context_and_empty_gold() -> None:
    text = "We need experience with Python, Kafka and distributed systems."
    gazetteer = _seed(
        [
            _record(
                record_id="a:1",
                job_id=1,
                host="jobs.a.test",
                text=text,
                candidates=["Kafka", "distributed systems"],
                risk=True,
            )
        ]
    )
    learned = copy.deepcopy(gazetteer)
    learned["records"][0]["shadow_candidates"] = ["Kafka"]

    queue = build_annotation_queue(gazetteer, learned, limit=10, context_tokens=3)

    assert queue["candidate_count"] == 2
    assert queue["selected_count"] == 2
    assert queue["split_groups"] == {"jobs.a.test": 2}
    assert queue["learned_proxy_positive_count"] == 1
    assert queue["gazetteer_only_count"] == 1
    assert queue["recall_risk_context_count"] == 2
    assert not any(queue["boundaries"].values())

    by_candidate = {row["candidate"]: row for row in queue["records"]}
    kafka = by_candidate["Kafka"]
    assert kafka["learned_proxy_positive"] is True
    assert kafka["evidence"] == "Kafka"
    assert text[kafka["span_start"] : kafka["span_end"]] == "Kafka"
    assert "Kafka" in kafka["context"]
    assert kafka["gold_label"] is None
    assert kafka["gold_subtype"] is None
    assert kafka["annotation_status"] == "unreviewed"

    distributed = by_candidate["distributed systems"]
    assert distributed["learned_proxy_positive"] is False
    assert text[distributed["span_start"] : distributed["span_end"]] == (
        "distributed systems"
    )


def test_queue_selection_is_deterministic_and_source_host_stratified() -> None:
    gazetteer = _seed(
        [
            _record(
                record_id="a:1",
                job_id=1,
                host="jobs.a.test",
                text="Python Kafka SQL",
                candidates=["Python", "Kafka", "SQL"],
                risk=False,
            ),
            _record(
                record_id="b:2",
                job_id=2,
                host="jobs.b.test",
                text="Docker Kubernetes Terraform",
                candidates=["Docker", "Kubernetes", "Terraform"],
                risk=True,
            ),
        ]
    )
    learned = copy.deepcopy(gazetteer)
    learned["records"][0]["shadow_candidates"] = ["Python"]
    learned["records"][1]["shadow_candidates"] = ["Docker"]

    first = build_annotation_queue(gazetteer, learned, limit=4)
    second = build_annotation_queue(gazetteer, learned, limit=4)

    assert first == second
    assert first["selected_count"] == 4
    assert first["split_group_count"] == 2
    assert set(first["split_groups"]) == {"jobs.a.test", "jobs.b.test"}
    assert all(row["selection_rank"] >= 1 for row in first["records"])


def test_queue_fails_closed_on_seed_drift_or_invalid_boundaries() -> None:
    gazetteer = _seed(
        [
            _record(
                record_id="a:1",
                job_id=1,
                host="jobs.a.test",
                text="Python Kafka",
                candidates=["Kafka"],
                risk=True,
            )
        ]
    )
    learned = copy.deepcopy(gazetteer)
    learned["records"][0]["requirement_text_sha256"] = "different"
    with pytest.raises(ValueError, match="text drift"):
        build_annotation_queue(gazetteer, learned)

    learned = copy.deepcopy(gazetteer)
    learned["boundaries"]["labels_invented"] = 1
    with pytest.raises(ValueError, match="violates annotation boundaries"):
        build_annotation_queue(gazetteer, learned)


def test_queue_rejects_ungrounded_candidate_and_invalid_limits() -> None:
    gazetteer = _seed(
        [
            _record(
                record_id="a:1",
                job_id=1,
                host="jobs.a.test",
                text="Python Kafka",
                candidates=["Kubernetes"],
                risk=True,
            )
        ]
    )
    learned = copy.deepcopy(gazetteer)
    with pytest.raises(ValueError, match="not grounded"):
        build_annotation_queue(gazetteer, learned)
    with pytest.raises(ValueError, match="limit"):
        build_annotation_queue(gazetteer, learned, limit=0)
    with pytest.raises(ValueError, match="token radius"):
        build_annotation_queue(gazetteer, learned, context_tokens=0)
