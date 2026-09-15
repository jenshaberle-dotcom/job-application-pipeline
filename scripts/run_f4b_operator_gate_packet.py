"""Build a read-only, privacy-bounded F4B operator decision packet.

The packet may compare approved private Candidate Fact capability tags with public
job-side requirement evidence in memory. It never emits Candidate Fact statements,
raw capability tags, fact keys, provenance, review rationales, or reviewer identity.
It grants no fit, hard-filter, ranking, Top-5, or application authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config

CAPABILITY_EVIDENCE_CLASSES = (
    "professional_employment",
    "formal_education",
    "portfolio_implementation",
    "training_certification",
)
CANONICAL_MINIMUM_QUALITY_SCORE = Decimal("70")


class OperatorGatePacketStop(RuntimeError):
    pass


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Mapping):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _normalize_label(value: object) -> str:
    text = str(value or "").strip().casefold()
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text


def classify_geography_candidate(
    *, country: object, work_model: object, commute_minutes: object
) -> tuple[str, str]:
    """Read-only projection of already-approved PD-020..023 semantics.

    This is calibration only. It deliberately models Germany-remote as admissible
    without commute evidence, while hybrid/onsite require an evidenced <=45 minute
    commute. Unknown job evidence remains unknown.
    """

    country_token = _normalize_label(country)
    if country_token in {"de", "deu", "deutschland", "germany"}:
        country_token = "de"
    model = _normalize_label(work_model).replace("_", "-")
    if not country_token:
        return "unknown", "job_country_missing"
    if country_token != "de":
        return "failed", "outside_approved_germany_boundary"
    if model == "remote":
        return "passed", "germany_remote_admissible_pd020_pd023"
    if model not in {"hybrid", "onsite"}:
        return "unknown", "job_work_model_missing_or_unresolved"
    if not isinstance(commute_minutes, int):
        return "unknown", "commute_evidence_required_for_regional_role"
    if commute_minutes <= 45:
        return "passed", "regional_commute_within_approved_45_minutes"
    return "failed", "regional_commute_exceeds_approved_45_minutes"


def _job_skills(sidecar: object) -> tuple[str, tuple[str, ...]]:
    if not isinstance(sidecar, Mapping):
        return "missing", ()
    fields = sidecar.get("fields")
    if not isinstance(fields, Mapping):
        return "invalid", ()
    skills = fields.get("job_skills")
    if not isinstance(skills, Mapping):
        return "missing", ()
    status = str(skills.get("status") or "missing")
    values = skills.get("values")
    if not isinstance(values, list):
        return status, ()
    normalized = tuple(
        sorted({_normalize_label(item) for item in values if _normalize_label(item)})
    )
    return status, normalized


def review_binding_status(
    row: Mapping[str, object],
    *,
    current_profile_sha256: str,
    valid_fact_keys: set[str],
) -> tuple[str, tuple[str, ...]]:
    if row.get("review_id") is None:
        return "missing", ("no_active_review",)
    reasons: list[str] = []
    if str(row.get("review_profile_sha256") or "") != current_profile_sha256:
        reasons.append("candidate_profile_hash_changed")
    if row.get("review_assessment_updated_at") != row.get("assessment_updated_at"):
        reasons.append("assessment_revision_changed")
    current_detail = ""
    ranking_factors = row.get("ranking_factors")
    if isinstance(ranking_factors, Mapping):
        current_detail = str(ranking_factors.get("detail_description_sha256") or "")
    if str(row.get("review_detail_sha256") or "") != current_detail:
        reasons.append("assessment_detail_hash_changed")
    raw_keys = row.get("review_fact_keys")
    keys = {str(value) for value in raw_keys} if isinstance(raw_keys, list) else set()
    if not keys:
        reasons.append("review_fact_refs_missing")
    elif not keys.issubset(valid_fact_keys):
        reasons.append("review_fact_refs_no_longer_valid")
    return ("exact_current", ()) if not reasons else ("stale", tuple(reasons))


def _coverage_bucket(match_count: int, total: int) -> str:
    if total <= 0:
        return "not_observed"
    if match_count == total:
        return "all_observed_skills_exactly_covered"
    if match_count == 0:
        return "no_observed_skill_exactly_covered"
    return "partial_exact_coverage"


def build_packet(
    *,
    rows: list[Mapping[str, object]],
    candidate_capability_tags: set[str],
    valid_fact_keys: set[str],
    profile_version: str,
    profile_sha256: str,
    runtime_minimum_quality_score: object,
    policy_version: str,
    source_sha: str,
) -> dict[str, object]:
    emitted: list[dict[str, object]] = []
    binding_counts: Counter[str] = Counter()
    geography_counts: Counter[str] = Counter()
    skill_counts: Counter[str] = Counter()
    hard_component_counts: dict[str, Counter[str]] = {
        key: Counter() for key in ("employment", "languages", "weekly_hours", "seniority_and_capability_fit")
    }

    for row in rows:
        binding, binding_reasons = review_binding_status(
            row,
            current_profile_sha256=profile_sha256,
            valid_fact_keys=valid_fact_keys,
        )
        binding_counts[binding] += 1
        geography_status, geography_reason = classify_geography_candidate(
            country=row.get("country"),
            work_model=row.get("work_model"),
            commute_minutes=row.get("commute_minutes"),
        )
        geography_counts[geography_status] += 1
        skill_status, observed_skills = _job_skills(row.get("sidecar_payload"))
        matched = sum(skill in candidate_capability_tags for skill in observed_skills)
        bucket = _coverage_bucket(matched, len(observed_skills))
        skill_counts[bucket] += 1
        hard_reasons = row.get("hard_filter_reasons")
        hard_reasons = hard_reasons if isinstance(hard_reasons, Mapping) else {}
        for key in hard_component_counts:
            hard_component_counts[key][str(hard_reasons.get(key) or "unknown")] += 1

        emitted.append(
            {
                "silver_job_id": int(row["silver_job_id"]),
                "company_name": str(row.get("company_name") or ""),
                "title": str(row.get("title") or ""),
                "source_name": str(row.get("source_name") or ""),
                "source_url": str(row.get("source_url") or ""),
                "origin_validation_status": str(row.get("origin_validation_status") or ""),
                "product_readiness_status": str(row.get("product_readiness_status") or ""),
                "hard_filter_status": str(row.get("hard_filter_status") or ""),
                "hard_filter_reasons": {
                    key: str(hard_reasons.get(key) or "unknown")
                    for key in hard_component_counts
                },
                "geography_calibration": {
                    "status": geography_status,
                    "reason": geography_reason,
                },
                "job_skill_evidence_status": skill_status,
                "observed_job_skill_count": len(observed_skills),
                "exact_candidate_skill_match_count": matched,
                "exact_candidate_skill_unmatched_count": len(observed_skills) - matched,
                "exact_candidate_skill_coverage": (
                    round(matched / len(observed_skills), 4) if observed_skills else None
                ),
                "capability_overlap_class": bucket,
                "active_capability_review_decision": (
                    str(row.get("review_decision")) if row.get("review_decision") is not None else None
                ),
                "capability_review_binding": binding,
                "capability_review_stale_reasons": list(binding_reasons),
                "sidecar_evidence_hash": str(row.get("sidecar_evidence_hash") or ""),
            }
        )

    runtime_threshold = Decimal(str(runtime_minimum_quality_score))
    threshold_match = runtime_threshold == CANONICAL_MINIMUM_QUALITY_SCORE

    # Prioritize stale reviews first, then evidence-rich current jobs, while keeping
    # the packet bounded. Candidate private content is never emitted.
    review_candidates = sorted(
        emitted,
        key=lambda item: (
            0 if item["capability_review_binding"] == "stale" else 1,
            0 if item["observed_job_skill_count"] else 1,
            -(item["exact_candidate_skill_coverage"] or -1),
            -item["observed_job_skill_count"],
            item["silver_job_id"],
        ),
    )[:12]

    serialized = json.dumps(emitted, sort_keys=True, ensure_ascii=False)
    forbidden = ("candidate_fact_keys", "review_rationale", "statement", "provenance", "candidate_capability_tags")
    if any(token in serialized for token in forbidden):
        raise OperatorGatePacketStop("PRIVATE_CANDIDATE_FACT_FIELD_LEAK")

    return {
        "schema": "jap.f4b.operator_gate_packet.v1",
        "source_sha": source_sha,
        "authority": "read_only_calibration_no_product_mutation",
        "candidate_profile": {
            "profile_version": profile_version,
            "payload_sha256": profile_sha256,
            "approved_capability_fact_count": len(valid_fact_keys),
            "private_values_emitted": False,
        },
        "ranking_threshold": {
            "runtime_minimum_quality_score": float(runtime_threshold),
            "canonical_pd051_minimum_quality_score": float(CANONICAL_MINIMUM_QUALITY_SCORE),
            "matches_canonical_pd051": threshold_match,
            "runtime_policy_version": policy_version,
        },
        "approved_geography_policy_projection": {
            "source_decisions": ["PD-020", "PD-021", "PD-022", "PD-023"],
            "calibration_only": True,
            "germany_remote_admissible": True,
            "regional_hybrid_onsite_commute_max_minutes": 45,
            "hybrid_preference_is_soft_not_hard": True,
        },
        "summary": {
            "current_job_count": len(emitted),
            "capability_review_binding": dict(sorted(binding_counts.items())),
            "geography_calibration": dict(sorted(geography_counts.items())),
            "capability_overlap": dict(sorted(skill_counts.items())),
            "hard_filter_components": {
                key: dict(sorted(counter.items())) for key, counter in hard_component_counts.items()
            },
        },
        "operator_review_sample": review_candidates,
        "rows": emitted,
        "next_decision_classes": {
            "technical_projection_not_new_preference_decision": [
                "materialize_or_otherwise project already-approved PD-020..023 geography/work-model boundaries without changing their meaning"
            ],
            "operator_confirmation_required": [
                "resolve runtime 60 versus canonical PD-051 70 minimum-quality authority",
                "approve a deterministic capability-fit rubric before exact skill overlap can become fit authority",
                "re-review stale exact-revision capability decisions; old decisions cannot be rebound automatically",
                "approve numeric Fit rubric and Combined-score formula only after enough current Fit evidence exists",
            ],
        },
        "boundaries": {
            "database_writes": False,
            "provider_calls": 0,
            "candidate_fact_private_values_emitted": False,
            "capability_fit_authority_changed": False,
            "hard_filter_authority_changed": False,
            "ranking_authority_changed": False,
            "top5_authority_changed": False,
            "application_authority_changed": False,
        },
    }


def _read_database() -> tuple[list[dict[str, object]], set[str], set[str], str, str, object, str]:
    with psycopg.connect(**get_database_config(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT profile_version, payload_sha256, status
                FROM candidate_fact_profiles
                WHERE profile_key = 'default'
                """
            )
            profile = cur.fetchone()
            if profile is None or str(profile["status"]) != "approved":
                raise OperatorGatePacketStop("APPROVED_CANDIDATE_PROFILE_MISSING")
            profile_version = str(profile["profile_version"])
            profile_sha = str(profile["payload_sha256"])

            cur.execute(
                """
                SELECT fact_key, capability_tags
                FROM candidate_facts
                WHERE profile_key = 'default'
                  AND approval_status = 'approved'
                  AND evidence_class = ANY(%s)
                  AND (valid_from IS NULL OR valid_from <= current_date)
                  AND (valid_until IS NULL OR valid_until >= current_date)
                """,
                (list(CAPABILITY_EVIDENCE_CLASSES),),
            )
            fact_rows = list(cur.fetchall())
            valid_fact_keys = {str(row["fact_key"]) for row in fact_rows}
            capability_tags: set[str] = set()
            for row in fact_rows:
                raw = row.get("capability_tags")
                if isinstance(raw, list):
                    capability_tags.update(
                        _normalize_label(value) for value in raw if _normalize_label(value)
                    )

            cur.execute(
                """
                SELECT status, minimum_quality_score, policy_version
                FROM product_v1_ranking_policy
                WHERE policy_key = 'default'
                """
            )
            policy = cur.fetchone()
            if policy is None or str(policy["status"]) != "approved":
                raise OperatorGatePacketStop("APPROVED_RANKING_POLICY_MISSING")

            cur.execute(
                """
                SELECT
                    readiness.silver_job_id,
                    readiness.company_name,
                    readiness.title,
                    readiness.source_name,
                    readiness.source_url,
                    readiness.origin_validation_status,
                    readiness.product_readiness_status,
                    current_job.city,
                    current_job.country,
                    assessment.work_model,
                    assessment.commute_minutes,
                    assessment.updated_at AS assessment_updated_at,
                    assessment.ranking_factors,
                    hard_filter.hard_filter_status,
                    hard_filter.hard_filter_reasons,
                    sidecar.evidence_hash AS sidecar_evidence_hash,
                    sidecar.evidence_payload AS sidecar_payload,
                    review.id AS review_id,
                    review.decision AS review_decision,
                    review.candidate_profile_sha256 AS review_profile_sha256,
                    review.assessment_detail_sha256 AS review_detail_sha256,
                    review.assessment_updated_at AS review_assessment_updated_at,
                    review.referenced_fact_keys AS review_fact_keys
                FROM gold_product_v1_job_readiness readiness
                JOIN gold_current_job_opportunities current_job
                  ON current_job.id = readiness.silver_job_id
                JOIN job_product_assessments assessment
                  ON assessment.silver_job_id = readiness.silver_job_id
                JOIN gold_product_v1_hard_filter_evaluation hard_filter
                  ON hard_filter.silver_job_id = readiness.silver_job_id
                LEFT JOIN silver_job_requirement_evidence sidecar
                  ON sidecar.silver_job_id = readiness.silver_job_id
                LEFT JOIN product_v1_capability_fit_reviews review
                  ON review.silver_job_id = readiness.silver_job_id
                 AND review.status = 'active'
                WHERE readiness.lifecycle_status = 'active_confirmed'
                ORDER BY readiness.silver_job_id
                """
            )
            rows = [dict(row) for row in cur.fetchall()]
        conn.rollback()
    return (
        rows,
        capability_tags,
        valid_fact_keys,
        profile_version,
        profile_sha,
        policy["minimum_quality_score"],
        str(policy["policy_version"] or ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    (
        rows,
        capability_tags,
        valid_fact_keys,
        profile_version,
        profile_sha,
        threshold,
        policy_version,
    ) = _read_database()
    packet = build_packet(
        rows=rows,
        candidate_capability_tags=capability_tags,
        valid_fact_keys=valid_fact_keys,
        profile_version=profile_version,
        profile_sha256=profile_sha,
        runtime_minimum_quality_score=threshold,
        policy_version=policy_version,
        source_sha=args.source_sha,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_json_safe(packet), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"summary": packet["summary"], "ranking_threshold": packet["ranking_threshold"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
