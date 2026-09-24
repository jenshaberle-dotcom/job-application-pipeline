"""Runtime binding for the Product V1 demo Application Workspace.

The default action is read-only context inspection for one explicit operator-selected
current employer-origin job. Existing Top-5 membership remains a stronger optional
authority, but is not required merely to prepare review text. An explicit
``--generate`` action produces a review-only source-grounded draft. It
prefers the existing bounded OpenAI drafter when a key is available and falls back
to a deterministic evidence-first package if no provider is available or the bounded
provider campaign cannot yield a validated package. Neither path performs any
database/application/submission/send write.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
from typing import Any, Mapping

import psycopg
from psycopg.rows import dict_row

from scripts.run_product_v1_assessment_materialization import (
    authorized_recurring_employer_origin_sources,
)
from src.config import get_database_config
from src.ingestion.repository import JobIngestionRepository
from src.search_intelligence.exact_observation_detail import bound_observation_detail
from src.search_intelligence.f6_template_authority import authority_status
from src.search_intelligence.product_v1_application_context import (
    OPERATOR_SELECTED_AUTHORITY_SOURCE,
    TOP5_AUTHORITY_SOURCE,
)
from src.search_intelligence.product_v1_application_drafter import (
    execute_product_v1_application_drafter,
    openai_application_draft_model_callback,
)
from src.search_intelligence.product_v1_application_workspace import (
    ApplicationWorkspaceStop,
    build_application_workspace_context,
    local_document_loader,
)
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_text,
)
from src.search_intelligence.product_v1_live_vacancy_revalidation import (
    revalidate_selected_vacancy,
)
from src.search_intelligence.product_v1_evidence_first_draft import (
    EvidenceFirstDraftStop,
    build_evidence_first_review_draft,
)


DEFAULT_OUTPUT = Path("/tmp/product_v1_application_workspace.json")


class ApplicationWorkspaceLifecycleStop(ApplicationWorkspaceStop):
    """Blocked F6 request after an authoritative lifecycle-health write."""

    def __init__(self, message: str, *, lifecycle_health_observation_writes: int) -> None:
        super().__init__(message)
        self.lifecycle_health_observation_writes = lifecycle_health_observation_writes
        self.database_writes = lifecycle_health_observation_writes


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _load_runtime_rows(
    silver_job_id: int,
) -> tuple[
    Mapping[str, object],
    str,
    Mapping[str, object] | None,
    tuple[Mapping[str, object], ...],
    tuple[Mapping[str, object], ...],
]:
    if silver_job_id <= 0:
        raise ApplicationWorkspaceStop("silver_job_id must be positive")

    conn = _connect()
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    SELECT *
                    FROM gold_product_v1_top_jobs
                    WHERE silver_job_id = %s
                    """,
                    (silver_job_id,),
                )
                target = cur.fetchone()
                target_authority_source = TOP5_AUTHORITY_SOURCE
                if target is None:
                    cur.execute(
                        """
                        SELECT *
                        FROM gold_product_v1_job_readiness
                        WHERE silver_job_id = %s
                        """,
                        (silver_job_id,),
                    )
                    target = cur.fetchone()
                    target_authority_source = OPERATOR_SELECTED_AUTHORITY_SOURCE
                if target is None:
                    raise ApplicationWorkspaceStop(
                        "current Product job was not found"
                    )

                cur.execute(
                    """
                    SELECT
                        observation.source_url AS latest_observation_source_url,
                        observation.normalized_evidence AS latest_observation_evidence,
                        observation.observed_at AS latest_observation_observed_at
                    FROM silver_jobs silver
                    LEFT JOIN LATERAL (
                        SELECT source_url, normalized_evidence, observed_at
                        FROM job_observations
                        WHERE raw_job_id = silver.raw_job_id
                          AND source_name = silver.source_name
                          AND is_seen = TRUE
                        ORDER BY observed_at DESC, id DESC
                        LIMIT 1
                    ) observation ON TRUE
                    WHERE silver.id = %s
                    """,
                    (silver_job_id,),
                )
                observation = cur.fetchone()
                target = dict(target)
                if observation is not None:
                    target.update(
                        {
                            "latest_observation_source_url": observation.get(
                                "latest_observation_source_url"
                            ),
                            "latest_observation_evidence": observation.get(
                                "latest_observation_evidence"
                            ),
                            "latest_observation_observed_at": observation.get(
                                "latest_observation_observed_at"
                            ),
                        }
                    )

                cur.execute(
                    """
                    SELECT status, payload_sha256
                    FROM candidate_fact_profiles
                    WHERE profile_key = 'default'
                    """
                )
                profile = cur.fetchone()

                cur.execute(
                    """
                    SELECT
                        fact_key,
                        category,
                        evidence_class,
                        approval_status,
                        statement,
                        capability_tags,
                        limitations,
                        valid_from,
                        valid_until
                    FROM candidate_facts
                    WHERE profile_key = 'default'
                    ORDER BY fact_key
                    """
                )
                facts = tuple(cur.fetchall())

                cur.execute(
                    """
                    SELECT DISTINCT ON (document_type)
                        document_type,
                        source_label,
                        source_reference,
                        content_sha256,
                        status
                    FROM application_source_documents
                    WHERE document_type IN ('base_cv', 'base_application_letter')
                      AND status = 'approved'
                    ORDER BY document_type, approved_at DESC NULLS LAST, id DESC
                    """
                )
                documents = tuple(cur.fetchall())
        conn.rollback()
    finally:
        conn.close()

    return target, target_authority_source, profile, facts, documents


def _private_document_root() -> Path | None:
    raw = os.environ.get("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", "").strip()
    return Path(raw).expanduser() if raw else None


def _employer_origin_authorized(source_name: object) -> bool:
    authorized = set(
        authorized_recurring_employer_origin_sources(JobIngestionRepository())
    )
    return str(source_name or "") in authorized


def load_application_workspace(
    silver_job_id: int,
) -> tuple[object, str, str, str, int]:
    target, target_authority_source, profile, facts, documents = _load_runtime_rows(
        silver_job_id
    )
    source_url = str(target.get("source_url") or "")
    source_name = str(target.get("source_name") or "")
    revalidation = revalidate_selected_vacancy(
        silver_job_id=silver_job_id,
        expected_source_name=source_name,
        expected_source_url=source_url,
    )
    if revalidation.closed:
        raise ApplicationWorkspaceLifecycleStop(
            "current vacancy is no longer available: "
            f"{revalidation.evidence_reason}",
            lifecycle_health_observation_writes=revalidation.health_observation_writes,
        )
    if not revalidation.active:
        raise ApplicationWorkspaceStop(
            "current vacancy could not be verified: "
            f"{revalidation.evidence_reason}"
        )

    persisted_detail = bound_observation_detail(target)
    if persisted_detail is not None:
        fetched_title, detail_text = persisted_detail
        final_url = source_url
        evidence_mode = "exact_persisted_observation"
        job_detail_http_gets = 0
    else:
        final_url, fetched_title, detail_text = fetch_public_https_detail_text(source_url)
        evidence_mode = "live_http_detail"
        job_detail_http_gets = 1

    context = build_application_workspace_context(
        top_job_row=target,
        detail_text=detail_text,
        profile_row=profile,
        fact_rows=facts,
        document_rows=documents,
        load_document=local_document_loader(private_root=_private_document_root()),
        as_of_date=date.today(),
        authority_source=target_authority_source,
        employer_origin_authorized=_employer_origin_authorized(
            target.get("source_name")
        ),
    )
    return context, final_url, fetched_title, evidence_mode, job_detail_http_gets


def application_workspace_payload(silver_job_id: int) -> dict[str, object]:
    context, final_url, fetched_title, evidence_mode, job_detail_http_gets = (
        load_application_workspace(silver_job_id)
    )
    canonical = context.canonical_payload()  # type: ignore[union-attr]
    approved_hashes = {
        document.document_type: document.content_sha256
        for document in context.source_documents  # type: ignore[union-attr]
    }
    return {
        "schema": "job_application_pipeline.product_v1_application_workspace.v1",
        "status": "ready" if context.generation_ready else "blocked",  # type: ignore[union-attr]
        "workspace": canonical,
        "template_authority": authority_status(approved_hashes),
        "live_job_evidence": {
            "final_url": final_url,
            "fetched_title": fetched_title,
            "detail_sha256": context.target.detail_sha256,  # type: ignore[union-attr]
            "evidence_mode": evidence_mode,
        },
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "vacancy_revalidation_http_gets": 1,
            "lifecycle_health_observation_writes": 0,
            "job_detail_http_gets": job_detail_http_gets,
            "current_observation_detail_reuse": int(
                evidence_mode == "exact_persisted_observation"
            ),
            "provider_requests": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
            "draft_approval_authority": False,
            "application_authority": False,
            "submission_authority": False,
            "top5_authority_required_for_operator_selected_drafting": False,
            "operator_selected_job_is_not_top5_authority": True,
            "hard_filter_unknown_does_not_become_passed": True,
        },
    }


def _evidence_first_draft_payload(
    *,
    context: object,
    final_url: str,
    fetched_title: str,
    evidence_mode: str,
    job_detail_http_gets: int,
    fallback_reason: str,
    provider_requests: int = 0,
    llm_requests: int = 0,
    estimated_model_cost_usd: float = 0.0,
    stages: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    try:
        package = build_evidence_first_review_draft(context)  # type: ignore[arg-type]
    except EvidenceFirstDraftStop as exc:
        raise ApplicationWorkspaceStop(str(exc)) from exc
    return {
        "schema": "job_application_pipeline.product_v1_application_draft_demo.v1",
        "status": "draft_for_review",
        "draft_mode": "deterministic_evidence_first",
        "fallback_reason": fallback_reason,
        "context_source_manifest": context.source_manifest(),  # type: ignore[union-attr]
        "package": package.canonical_payload(),
        "stages": stages or [
            {
                "stage": "deterministic",
                "attempted": True,
                "status": "draft_for_review",
                "reason_code": "source_grounded_evidence_first_fallback",
                "provider_requests": 0,
            }
        ],
        "provider_requests": provider_requests,
        "llm_requests": llm_requests,
        "tavily_requests": 0,
        "estimated_model_cost_usd": round(float(estimated_model_cost_usd), 8),
        "database_writes": 0,
        "job_detail_http_gets": job_detail_http_gets,
        "current_observation_detail_reuse": int(
            evidence_mode == "exact_persisted_observation"
        ),
        "application_writes": 0,
        "submission_writes": 0,
        "send_actions": 0,
        "draft_approval_authority": False,
        "application_authority": False,
        "submission_authority": False,
        "product_authority": False,
        "live_job_evidence": {
            "final_url": final_url,
            "fetched_title": fetched_title,
            "detail_sha256": context.target.detail_sha256,  # type: ignore[union-attr]
            "evidence_mode": evidence_mode,
        },
    }


def generate_application_draft_payload(silver_job_id: int) -> dict[str, object]:
    context, final_url, fetched_title, evidence_mode, job_detail_http_gets = (
        load_application_workspace(silver_job_id)
    )
    if not context.generation_ready:
        return {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v1",
            "status": "blocked",
            "blocked_reasons": list(context.blocked_reasons),
            "workspace": context.canonical_payload(),
            "provider_requests": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        }
    if not context.claim_plan:
        return {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v1",
            "status": "blocked",
            "blocked_reasons": ["candidate_job_claim_plan_required"],
            "workspace": context.canonical_payload(),
            "provider_requests": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        }

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _evidence_first_draft_payload(
            context=context,
            final_url=final_url,
            fetched_title=fetched_title,
            evidence_mode=evidence_mode,
            job_detail_http_gets=job_detail_http_gets,
            fallback_reason="provider_key_unavailable",
        )

    execution = execute_product_v1_application_drafter(
        context=context,
        model=openai_application_draft_model_callback(
            context=context,
            api_key=api_key,
        ),
    )
    if execution.package is None:
        return _evidence_first_draft_payload(
            context=context,
            final_url=final_url,
            fetched_title=fetched_title,
            evidence_mode=evidence_mode,
            job_detail_http_gets=job_detail_http_gets,
            fallback_reason="provider_campaign_unresolved",
            provider_requests=execution.provider_requests,
            llm_requests=execution.llm_requests,
            estimated_model_cost_usd=execution.estimated_model_cost_usd,
            stages=[stage.to_json() for stage in execution.stages],
        )

    payload = execution.to_json()
    payload.update(
        {
            "schema": "job_application_pipeline.product_v1_application_draft_demo.v1",
            "status": "draft_for_review",
            "draft_mode": "provider_validated",
            "fallback_reason": None,
            "live_job_evidence": {
                "final_url": final_url,
                "fetched_title": fetched_title,
                "detail_sha256": context.target.detail_sha256,
                "evidence_mode": evidence_mode,
            },
        }
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--silver-job-id", type=int, required=True)
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = (
            generate_application_draft_payload(args.silver_job_id)
            if args.generate
            else application_workspace_payload(args.silver_job_id)
        )
    except ApplicationWorkspaceStop as exc:
        payload = {
            "schema": "job_application_pipeline.product_v1_application_workspace.v1",
            "status": "blocked",
            "blocked_reasons": [str(exc)],
            "provider_requests": 0,
            "database_writes": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print("============================================")
    print("PRODUCT V1 APPLICATION WORKSPACE")
    print("============================================")
    print(f"STATUS={str(payload.get('status') or 'unknown').upper()}")
    print(f"SILVER_JOB_ID={args.silver_job_id}")
    print(f"DRAFT_MODE={payload.get('draft_mode', 'NONE')}")
    print(f"PROVIDER_REQUESTS={payload.get('provider_requests', 0)}")
    print(f"DATABASE_WRITES={payload.get('database_writes', 0)}")
    print(f"SUBMISSION_WRITES={payload.get('submission_writes', 0)}")
    print(f"SEND_ACTIONS={payload.get('send_actions', 0)}")
    print(f"artifact={args.output.resolve()}")
    print("PRODUCT_V1_APPLICATION_WORKSPACE=COMPLETE")
    return 0 if payload.get("status") in {"ready", "draft_for_review"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
