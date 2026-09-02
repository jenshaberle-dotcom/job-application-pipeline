"""Runtime binding for the Product V1 demo Application Workspace.

The default action is read-only context inspection for one authoritative Top-5 job.
An explicit ``--generate`` action produces a review-only source-grounded draft. It
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
from src.search_intelligence.product_v1_evidence_first_draft import (
    EvidenceFirstDraftStop,
    build_evidence_first_review_draft,
)


DEFAULT_OUTPUT = Path("/tmp/product_v1_application_workspace.json")


def _connect() -> psycopg.Connection[Any]:
    return psycopg.connect(**get_database_config(), row_factory=dict_row)


def _load_runtime_rows(
    silver_job_id: int,
) -> tuple[
    Mapping[str, object],
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
                if target is None:
                    raise ApplicationWorkspaceStop(
                        "authoritative Top-5 job was not found"
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

    return target, profile, facts, documents


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
) -> tuple[object, str, str]:
    target, profile, facts, documents = _load_runtime_rows(silver_job_id)
    source_url = str(target.get("source_url") or "")
    final_url, fetched_title, detail_text = fetch_public_https_detail_text(source_url)
    context = build_application_workspace_context(
        top_job_row=target,
        detail_text=detail_text,
        profile_row=profile,
        fact_rows=facts,
        document_rows=documents,
        load_document=local_document_loader(private_root=_private_document_root()),
        as_of_date=date.today(),
        employer_origin_authorized=_employer_origin_authorized(
            target.get("source_name")
        ),
    )
    return context, final_url, fetched_title


def application_workspace_payload(silver_job_id: int) -> dict[str, object]:
    context, final_url, fetched_title = load_application_workspace(silver_job_id)
    canonical = context.canonical_payload()  # type: ignore[union-attr]
    return {
        "schema": "job_application_pipeline.product_v1_application_workspace.v1",
        "status": "ready" if context.generation_ready else "blocked",  # type: ignore[union-attr]
        "workspace": canonical,
        "live_job_evidence": {
            "final_url": final_url,
            "fetched_title": fetched_title,
            "detail_sha256": context.target.detail_sha256,  # type: ignore[union-attr]
        },
        "boundaries": {
            "database_reads": True,
            "database_writes": False,
            "job_detail_http_gets": 1,
            "provider_requests": 0,
            "application_writes": 0,
            "submission_writes": 0,
            "send_actions": 0,
            "draft_approval_authority": False,
            "application_authority": False,
            "submission_authority": False,
        },
    }


def _evidence_first_draft_payload(
    *,
    context: object,
    final_url: str,
    fetched_title: str,
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
        },
    }


def generate_application_draft_payload(silver_job_id: int) -> dict[str, object]:
    context, final_url, fetched_title = load_application_workspace(silver_job_id)
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
