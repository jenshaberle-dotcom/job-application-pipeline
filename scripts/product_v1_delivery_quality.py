"""RCC delivery stages: fresh vacancy checks, missing assessments, bound affinity.

No source activation, submission, mail action or synthetic score. Every write is
covered by the delivery journal and the existing identity/policy concurrency guards.
"""
from __future__ import annotations

def maintain_source(source_name, journal):
    from scripts import run_product_v1_assessment_materialization as materializer
    from scripts import run_product_v1_assessment_materialization_resilient as resilient
    from scripts import run_product_v1_assessment_detail_refresh as refresh
    from scripts import run_f4b_affinity_authority as affinity
    from src.job_lifecycle_health import JobLifecycleHealthRepository, fetch_exact_detail, classify_exact_detail
    from src.ingestion.repository import JobIngestionRepository

    authorized = materializer.authorized_recurring_employer_origin_sources(JobIngestionRepository())
    if source_name not in authorized:
        raise ValueError('QUALITY_SOURCE_NOT_AUTHORIZED')
    with affinity.connect() as conn:
        rows = conn.execute("SELECT silver_job_id FROM gold_product_v1_job_readiness WHERE source_name=%s AND lifecycle_status IN ('active_confirmed','unverifiable','stale_needs_refresh') ORDER BY silver_job_id", (source_name,)).fetchall()
    ids = [int(row['silver_job_id']) for row in rows]
    health = JobLifecycleHealthRepository()
    summary = dict(total=len(ids), checked=0, assessed=0, scored=0, unavailable=0, blocked=[])
    for job_id in ids:
        prefix = source_name + ':' + str(job_id)
        try:
            def check():
                target = health.load_target(job_id)
                if target.source_name != source_name:
                    raise ValueError('QUALITY_IDENTITY_CHANGED')
                result = classify_exact_detail(target, fetch_exact_detail(target.source_url, timeout_seconds=12))
                health.append_health_observation(expected_target=target, classification=result,
                    observed_by='rcc_product_quality_v1')
                return dict(outcome=result.outcome, reason=result.evidence_reason)
            result = journal.stage('health:' + prefix, check, effect=True)
            summary['checked'] += 1
            if result['outcome'] != 'seen_active':
                summary['unavailable'] += 1
                continue

            def assess():
                with affinity.connect() as conn:
                    ranking, filters = materializer._load_policy_versions(conn)
                    candidates = materializer._load_candidate_rows(conn, source_names=[source_name], silver_job_ids=[job_id])
                if candidates:
                    # Fresh detail evidence, not a cached old observation. A changed
                    # second read fails the canonical apply guard rather than guessing.
                    plan = materializer.build_plan(rows=candidates, authorized_sources=authorized,
                        ranking_policy_version=ranking, hard_filter_policy_version=filters,
                        fetch_detail=resilient.fetch_detail_isolated)
                    if plan['blocked_count']:
                        raise ValueError('ASSESSMENT_EVIDENCE_INCOMPLETE')
                    applied = materializer.apply_plan(plan=plan, source_names=[source_name],
                        silver_job_ids=[job_id], role_relevant_only=False, authorized_sources=authorized)
                    return dict(inserted=applied['inserted'], already_materialized=applied['already_materialized'])
                with refresh.connect() as conn:
                    row = refresh.load_current_row(conn, silver_job_id=job_id)
                    url, _, detail = refresh.fetch_public_https_detail_text(str(row['source_url']))
                    plan = refresh.build_refresh_plan(row=row, authorized_sources=authorized, final_url=url, detail_text=detail)
                    conn.rollback()
                    changed = refresh.apply_refresh(conn, expected_plan=plan, authorized_sources=authorized,
                        applied_by='rcc_product_quality_v1')
                    conn.commit()
                return dict(refreshed=changed)
            journal.stage('assessment:' + prefix, assess, effect=True)
            summary['assessed'] += 1

            def score():
                with affinity.connect() as conn:
                    policy, candidates, skipped = affinity._plan(conn, [job_id])
                    if skipped or len(candidates) != 1:
                        raise ValueError('AFFINITY_EXACT_EVIDENCE_REQUIRED')
                    changed = affinity._apply_one(conn, candidate=candidates[0], policy_version=policy.policy_version,
                        reviewed_by='rcc_product_quality_v1')
                    conn.commit()
                return dict(changed=changed)
            journal.stage('affinity:' + prefix, score, effect=True)
            summary['scored'] += 1
        except Exception as exc:
            summary['blocked'].append(dict(silver_job_id=job_id, error_type=type(exc).__name__))
        print(__import__('json').dumps(dict(stage='quality', source=source_name, completed=summary['checked'],
            total=len(ids), scored=summary['scored'], blocked=len(summary['blocked']))), flush=True)
    return summary
