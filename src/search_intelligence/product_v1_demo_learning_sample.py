"""Demo-only 10-job learning sample selector.

This module deliberately does not change the canonical Product role classifier.
It selects a bounded sample for the live demo so Candidate Fit, Affinity, hard
filters and ranking can be exercised on a broader real Employer-Origin cohort:

- five Candidate-Fact-backed live jobs from the employer with the largest current
  eligible inventory; and
- one target-interest job from each of five other employers.

No company name or job id is embedded here.  The downstream Product authorities
remain unchanged and decide fit/rankability.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping, Sequence

from src.job_lifecycle_health import OUTCOME_SEEN_ACTIVE
from src.search_intelligence.product_v1_contenders import has_phrase


DEMO_SAMPLE_SIZE = 10
ANCHOR_JOB_COUNT = 5
PEER_EMPLOYER_COUNT = 5
INTEREST_PHRASES = (
    "machine learning",
    "ml engineer",
    "mlops",
    "ai",
    "artificial intelligence",
    "data",
    "analytics",
    "platform",
    "reliability",
)


class DemoLearningSampleStop(RuntimeError):
    pass


def _facts(row: Mapping[str, object]) -> int:
    return int(row.get("matched_fact_count") or 0)


def _eligible(row: Mapping[str, object]) -> bool:
    matches = row.get("candidate_fact_matches")
    return (
        row.get("live_outcome") == OUTCOME_SEEN_ACTIVE
        and row.get("geography_eligible") is True
        and isinstance(matches, list)
        and bool(matches)
    )


def _interest_score(row: Mapping[str, object]) -> int:
    title = str(row.get("title") or "")
    return sum(1 for phrase in INTEREST_PHRASES if has_phrase(title, phrase))


def _job_sort_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        0 if row.get("role_relevant") is True else 1,
        -_interest_score(row),
        -_facts(row),
        int(row.get("silver_job_id") or 0),
    )


def select_demo_learning_sample(
    rows: Sequence[Mapping[str, object]],
    *,
    candidate_cap: int = DEMO_SAMPLE_SIZE,
) -> list[dict[str, object]]:
    if candidate_cap != DEMO_SAMPLE_SIZE:
        raise DemoLearningSampleStop(
            f"demo learning sample requires candidate_cap={DEMO_SAMPLE_SIZE}"
        )

    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if not _eligible(row):
            continue
        company = " ".join(str(row.get("company_name") or "").split()).strip()
        if not company:
            continue
        grouped[company].append(row)

    if len(grouped) < PEER_EMPLOYER_COUNT + 1:
        raise DemoLearningSampleStop(
            "demo learning sample needs at least six eligible employers"
        )

    anchor_company, anchor_rows = sorted(
        grouped.items(),
        key=lambda item: (-len(item[1]), item[0].casefold()),
    )[0]
    if len(anchor_rows) < ANCHOR_JOB_COUNT:
        raise DemoLearningSampleStop(
            "largest eligible employer has fewer than five live fact-backed jobs"
        )

    anchor_selected = sorted(
        anchor_rows,
        key=lambda row: (
            -_facts(row),
            -_interest_score(row),
            int(row.get("silver_job_id") or 0),
        ),
    )[:ANCHOR_JOB_COUNT]

    peer_candidates: list[tuple[tuple[object, ...], str, Mapping[str, object]]] = []
    for company, company_rows in grouped.items():
        if company == anchor_company:
            continue
        best = sorted(company_rows, key=_job_sort_key)[0]
        peer_rank = (
            0 if best.get("role_relevant") is True else 1,
            -_interest_score(best),
            -_facts(best),
            -len(company_rows),
            company.casefold(),
        )
        peer_candidates.append((peer_rank, company, best))

    peer_candidates.sort(key=lambda item: item[0])
    peer_selected = [
        row for _rank, _company, row in peer_candidates[:PEER_EMPLOYER_COUNT]
    ]
    if len(peer_selected) != PEER_EMPLOYER_COUNT:
        raise DemoLearningSampleStop("demo learning sample peer employer shortfall")

    selected = [dict(row) for row in (*anchor_selected, *peer_selected)]
    if len(selected) != DEMO_SAMPLE_SIZE:
        raise DemoLearningSampleStop("demo learning sample cardinality drift")
    return selected


__all__ = [
    "ANCHOR_JOB_COUNT",
    "DEMO_SAMPLE_SIZE",
    "DemoLearningSampleStop",
    "PEER_EMPLOYER_COUNT",
    "select_demo_learning_sample",
]
