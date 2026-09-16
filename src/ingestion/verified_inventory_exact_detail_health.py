"""Append-only exact-detail health writes after complete-inventory authority.

This writer exists for one narrow authority transition: a caller has already
proved source-level complete-inventory authority independently of historical
Bronze/Silver ``source_type`` projection and now needs to persist a stronger
exact-detail observation for one immutable vacancy identity.

The ordinary ``JobLifecycleHealthRepository.append_health_observation`` remains
unchanged and continues to require historical employer-origin source-type
authority. This class deliberately does not weaken that general contract.
"""
from __future__ import annotations

import json

from src.job_lifecycle_health import (
    COVERAGE_EXACT_DETAIL,
    OUTCOME_CLOSED,
    OUTCOME_SEEN_ACTIVE,
    HealthClassification,
    JobHealthTarget,
    JobLifecycleHealthRepository,
    ensure_expected_target_identity,
)


_ALLOWED_OUTCOMES = frozenset({OUTCOME_SEEN_ACTIVE, OUTCOME_CLOSED})


class VerifiedInventoryExactDetailHealthRepository(JobLifecycleHealthRepository):
    """Health repository for exact-detail follow-up to proven inventory authority."""

    def append_verified_inventory_exact_detail_health_observation(
        self,
        *,
        expected_target: JobHealthTarget,
        classification: HealthClassification,
        observed_by: str,
        ingestion_run_id: int | None = None,
    ) -> int:
        observer = observed_by.strip()
        if not observer:
            raise ValueError("observed_by must not be empty")
        if classification.coverage != COVERAGE_EXACT_DETAIL:
            raise ValueError(
                "verified-inventory follow-up only accepts exact_detail coverage"
            )
        if classification.outcome not in _ALLOWED_OUTCOMES:
            raise ValueError(
                "verified-inventory follow-up only accepts seen_active/closed outcomes"
            )

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self._target_query(for_update=True),
                    (expected_target.silver_job_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(
                        "Silver job disappeared before verified-inventory apply: "
                        f"{expected_target.silver_job_id}"
                    )

                current_target = self._target_from_row(row)
                ensure_expected_target_identity(
                    current_target,
                    expected_source_name=expected_target.source_name,
                    expected_source_url=expected_target.source_url,
                )
                if current_target != expected_target:
                    raise ValueError(
                        "Target identity drifted between verified-inventory probe and apply"
                    )

                cur.execute(
                    "INSERT INTO job_health_observations ("
                    "raw_job_id, ingestion_run_id, source_name, "
                    "external_job_id, source_url, outcome, coverage, "
                    "evidence_reason, evidence, observed_by"
                    ") VALUES ("
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s"
                    ") RETURNING id",
                    (
                        current_target.raw_job_id,
                        (
                            ingestion_run_id
                            if ingestion_run_id is not None
                            else current_target.ingestion_run_id
                        ),
                        current_target.source_name,
                        current_target.external_job_id,
                        current_target.source_url,
                        classification.outcome,
                        classification.coverage,
                        classification.evidence_reason,
                        json.dumps(
                            classification.evidence,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        observer,
                    ),
                )
                inserted = cur.fetchone()
                if inserted is None:
                    raise RuntimeError(
                        "verified-inventory health observation insert returned no id"
                    )
                observation_id = int(inserted["id"])

            conn.commit()

        return observation_id


__all__ = ["VerifiedInventoryExactDetailHealthRepository"]
