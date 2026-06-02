-- S7P/S7O Connector Build Queue Self-Repair Guard
--
-- Purpose:
--   Prevent the connector build candidate queue from repeatedly recommending
--   the same URL repair after a reviewed repair candidate has already been
--   applied to employer_origin_source_candidates.candidate_url.
--
-- Boundary:
--   Read-only Gold view replacement only. This migration does not build
--   connector artifacts, register connectors, activate sources, write Bronze
--   records or change scheduler configuration.

create or replace view gold_connector_build_candidate_queue as
with latest_feasibility_item as (
    select distinct on (i.candidate_id)
        i.review_id,
        i.candidate_id,
        i.company_key,
        i.company_name,
        i.origin_url,
        i.source_name_candidate,
        i.status as feasibility_candidate_status,
        i.risk_level as feasibility_candidate_risk_level,
        i.http_status,
        i.reachable,
        i.page_type,
        i.sample_job_count,
        i.sample_job_urls,
        i.feasibility_status,
        i.decision as feasibility_decision,
        i.blocker_code,
        i.reason as feasibility_reason,
        i.recommended_next_action as feasibility_next_action,
        i.url_quality_status,
        i.url_quality_feedback_code,
        i.url_repair_candidate_url,
        i.structural_job_evidence_count,
        i.job_search_page_evidence_count,
        i.job_detail_candidate_evidence_count,
        i.career_context_evidence_count,
        i.rejected_noise_count,
        i.evidence_classification,
        i.created_at as feasibility_created_at,
        r.created_at as review_created_at,
        r.reviewed_by as feasibility_reviewed_by
    from connector_feasibility_review_items i
    join connector_feasibility_reviews r on r.id = i.review_id
    order by i.candidate_id, r.created_at desc, i.id desc
),
queue as (
    select
        l.candidate_id,
        coalesce(g.company_key, l.company_key) as company_key,
        coalesce(g.display_company_name, l.company_name) as display_company_name,
        coalesce(g.candidate_url, l.origin_url) as candidate_url,
        coalesce(g.source_name_candidate, l.source_name_candidate) as source_name_candidate,
        g.source_type_candidate,
        g.candidate_status,
        g.candidate_risk_level,
        g.current_stage,
        g.fn_pressure_level,
        g.fn_pressure_reason,
        g.build_status,
        g.build_recommendation,
        g.build_mode,
        g.connector_module_path,
        g.connector_test_path,
        g.connector_docs_path,
        l.review_id as feasibility_review_id,
        l.feasibility_status,
        l.feasibility_decision,
        l.blocker_code,
        l.url_quality_status,
        l.url_quality_feedback_code,
        l.url_repair_candidate_url,
        l.http_status,
        l.reachable,
        l.page_type,
        l.sample_job_count,
        l.sample_job_urls,
        l.structural_job_evidence_count,
        l.job_search_page_evidence_count,
        l.job_detail_candidate_evidence_count,
        l.career_context_evidence_count,
        l.rejected_noise_count,
        l.feasibility_reason,
        l.feasibility_next_action,
        l.evidence_classification,
        l.feasibility_reviewed_by,
        l.review_created_at,
        case
            when g.candidate_status = 'active_controlled'
                then 'monitor_existing_source'
            when g.build_status in ('build_approval_required', 'artifact_generation_allowed', 'artifacts_present')
                then 'continue_existing_build_flow'
            when l.feasibility_status = 'likely_feasible'
                 and l.feasibility_decision = 'continue_to_connector_build_planning'
                 and l.url_quality_status = 'valid_probe_ready'
                 and l.job_detail_candidate_evidence_count > 0
                then 'build_candidate_recommended'
            when l.url_quality_status = 'repair_candidate_detected'
                 and l.url_repair_candidate_url is not null
                 and l.url_repair_candidate_url = coalesce(g.candidate_url, l.origin_url)
                then 'origin_source_discovery_required'
            when l.url_quality_status = 'repair_candidate_detected'
                 and l.url_repair_candidate_url is not null
                then 'origin_url_repair_required'
            when l.url_quality_status = 'structural_without_detail'
                then 'sample_job_review_required'
            when l.feasibility_status = 'missing_origin_url'
                 or l.url_quality_status in ('missing_origin_url', 'not_reachable')
                then 'origin_source_discovery_required'
            when l.url_quality_status in ('asset_noise_only', 'career_page_without_job_structure', 'unsafe_or_aggregator_url')
                then 'manual_source_review_required'
            else 'monitor_or_manual_review'
        end as queue_action,
        case
            when g.candidate_status = 'active_controlled' then 90
            when g.build_status = 'build_approval_required' then 10
            when g.build_status = 'artifact_generation_allowed' then 11
            when g.build_status = 'artifacts_present' then 12
            when l.feasibility_status = 'likely_feasible'
                 and l.feasibility_decision = 'continue_to_connector_build_planning'
                 and l.url_quality_status = 'valid_probe_ready'
                 and l.job_detail_candidate_evidence_count > 0
                then 20
            when l.url_quality_status = 'repair_candidate_detected'
                 and l.url_repair_candidate_url is not null
                 and l.url_repair_candidate_url = coalesce(g.candidate_url, l.origin_url)
                then 50
            when l.url_quality_status = 'repair_candidate_detected'
                 and l.url_repair_candidate_url is not null
                then 30
            when l.url_quality_status = 'structural_without_detail' then 40
            when l.feasibility_status = 'missing_origin_url'
                 or l.url_quality_status in ('missing_origin_url', 'not_reachable')
                then 50
            else 70
        end as queue_priority,
        case
            when g.candidate_status = 'active_controlled'
                then 'Candidate is already an active controlled source; monitor source value instead of creating another build item.'
            when g.build_status in ('build_approval_required', 'artifact_generation_allowed', 'artifacts_present')
                then 'A connector build flow already exists; continue the existing approval, generation or validation path.'
            when l.feasibility_status = 'likely_feasible'
                 and l.feasibility_decision = 'continue_to_connector_build_planning'
                 and l.url_quality_status = 'valid_probe_ready'
                 and l.job_detail_candidate_evidence_count > 0
                then 'Latest feasibility probe found reachable origin source and concrete job-detail evidence; prepare connector build planning.'
            when l.url_quality_status = 'repair_candidate_detected'
                 and l.url_repair_candidate_url is not null
                 and l.url_repair_candidate_url = coalesce(g.candidate_url, l.origin_url)
                then 'Repair candidate equals current URL; rerun origin source discovery or manual URL review instead of repeating the same repair.'
            when l.url_quality_status = 'repair_candidate_detected'
                 and l.url_repair_candidate_url is not null
                then 'Latest feasibility probe found a likely URL repair candidate; repair candidate_url before connector build planning.'
            when l.url_quality_status = 'structural_without_detail'
                then 'Latest feasibility probe found job-list structure but no concrete job-detail evidence; review samples or improve detail extraction.'
            when l.feasibility_status = 'missing_origin_url'
                 or l.url_quality_status in ('missing_origin_url', 'not_reachable')
                then 'Candidate needs renewed origin URL discovery before connector build planning.'
            when l.url_quality_status in ('asset_noise_only', 'career_page_without_job_structure', 'unsafe_or_aggregator_url')
                then 'Latest feasibility signal is not sufficient for build planning and needs manual source review.'
            else 'No immediate connector-build action was derived from the latest feasibility evidence.'
        end as queue_reason,
        case
            when g.build_status in ('build_approval_required', 'artifact_generation_allowed', 'artifacts_present')
                then g.debug_next_command
            when l.feasibility_status = 'likely_feasible'
                 and l.feasibility_decision = 'continue_to_connector_build_planning'
                 and l.url_quality_status = 'valid_probe_ready'
                 and l.job_detail_candidate_evidence_count > 0
                then 'python -m scripts.run_approval_gated_connector_build_agent --company-key '
                     || coalesce(g.company_key, l.company_key) || ' --reviewed-by jens --write'
            when l.url_quality_status = 'repair_candidate_detected'
                 and l.url_repair_candidate_url is not null
                 and l.url_repair_candidate_url = coalesce(g.candidate_url, l.origin_url)
                then 'repair candidate equals current URL; rerun origin source discovery or manual URL review'
            when l.url_quality_status = 'repair_candidate_detected'
                 and l.url_repair_candidate_url is not null
                then 'review repair candidate_url: ' || l.url_repair_candidate_url
            when l.url_quality_status = 'structural_without_detail'
                then 'review source manually or improve detail extraction before build planning'
            when l.feasibility_status = 'missing_origin_url'
                 or l.url_quality_status in ('missing_origin_url', 'not_reachable')
                then 'rerun origin source discovery / manual URL review before feasibility probe'
            else null::text
        end as recommended_command_or_review,
        greatest(
            coalesce(g.last_signal_at, l.review_created_at),
            l.review_created_at
        ) as last_signal_at
    from latest_feasibility_item l
    left join gold_candidate_lifecycle_status g on g.candidate_id = l.candidate_id
)
select *
from queue
order by queue_priority, last_signal_at desc nulls last, display_company_name;
