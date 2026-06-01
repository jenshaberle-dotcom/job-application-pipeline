-- S7A Gold Market Coverage & Candidate Lifecycle Foundation
-- Purpose: provide dashboard-ready read models for the Search Intelligence Control Center.
-- Boundary: read-only Gold views; no crawling, no source activation, no Bronze writes, no scheduler changes.

create or replace view gold_candidate_lifecycle_status as
with gate_summary as (
    select
        candidate_id,
        count(*)::integer as total_gate_count,
        count(*) filter (where gate_status = 'passed')::integer as passed_gate_count,
        count(*) filter (where gate_status in ('manual_review_required', 'failed', 'deferred'))::integer as blocked_gate_count,
        min(gate_order) filter (where gate_status in ('manual_review_required', 'failed', 'deferred')) as first_blocking_gate_order
    from employer_origin_candidate_gate_reviews
    group by candidate_id
),
blocking_gate as (
    select distinct on (candidate_id)
        candidate_id,
        gate_name as blocking_gate,
        gate_status as blocking_gate_status,
        decision as blocking_decision,
        stop_reason as blocker_reason,
        reviewed_at as blocking_reviewed_at
    from employer_origin_candidate_gate_reviews
    where gate_status in ('manual_review_required', 'failed', 'deferred')
    order by candidate_id, gate_order, updated_at desc
),
latest_fn_pressure as (
    select distinct on (candidate_id)
        candidate_id,
        risk_level as fn_pressure_level,
        sighting_count as fn_sighting_count,
        recent_sighting_count as fn_recent_sighting_count,
        last_observed_at as fn_last_observed_at,
        suggested_search_terms as fn_suggested_search_terms,
        reason as fn_pressure_reason,
        created_at as fn_snapshot_created_at
    from false_negative_risk_snapshots
    where candidate_id is not null
    order by candidate_id, created_at desc, id desc
),
latest_generation_plan as (
    select distinct on (candidate_id)
        candidate_id,
        generation_status,
        recommendation as generation_recommendation,
        next_command as generation_next_command,
        updated_at as generation_updated_at
    from employer_origin_connector_generation_plans
    order by candidate_id, updated_at desc, id desc
),
latest_build_request as (
    select distinct on (candidate_id)
        candidate_id,
        build_status,
        recommendation as build_recommendation,
        build_mode,
        next_command as build_next_command,
        connector_module_path,
        connector_test_path,
        connector_docs_path,
        updated_at as build_updated_at
    from employer_origin_connector_build_requests
    order by candidate_id, updated_at desc, id desc
),
term_suggestions as (
    select
        candidate_id,
        count(*)::integer as search_term_suggestion_count,
        count(*) filter (where status in ('proposed', 'accepted'))::integer as open_search_term_suggestion_count,
        max(updated_at) as latest_search_term_suggestion_at
    from search_term_suggestions
    group by candidate_id
)
select
    c.id as candidate_id,
    c.company_key,
    c.company_name as display_company_name,
    c.candidate_url,
    c.source_name_candidate,
    c.source_family_candidate,
    c.source_target_candidate,
    c.source_type_candidate,
    'origin_validation_ground_truth'::text as source_role,
    c.status as candidate_status,
    c.risk_level as candidate_risk_level,
    coalesce(gs.total_gate_count, 0) as total_gate_count,
    coalesce(gs.passed_gate_count, 0) as passed_gate_count,
    coalesce(gs.blocked_gate_count, 0) as blocked_gate_count,
    case
        when coalesce(gs.total_gate_count, 0) = 0 then 0::numeric(5,2)
        else round((coalesce(gs.passed_gate_count, 0)::numeric / gs.total_gate_count::numeric), 2)::numeric(5,2)
    end as gate_progress_ratio,
    bg.blocking_gate,
    bg.blocking_gate_status,
    bg.blocking_decision,
    bg.blocker_reason,
    fp.fn_pressure_level,
    fp.fn_sighting_count,
    fp.fn_recent_sighting_count,
    fp.fn_last_observed_at,
    fp.fn_suggested_search_terms,
    fp.fn_pressure_reason,
    gp.generation_status,
    gp.generation_recommendation,
    br.build_status,
    br.build_recommendation,
    br.build_mode,
    br.connector_module_path,
    br.connector_test_path,
    br.connector_docs_path,
    coalesce(ts.search_term_suggestion_count, 0) as search_term_suggestion_count,
    coalesce(ts.open_search_term_suggestion_count, 0) as open_search_term_suggestion_count,
    case
        when c.status = 'active_controlled' then 'active_controlled'
        when br.build_status = 'build_approval_required' then 'build_approval_required'
        when br.build_status = 'artifact_generation_allowed' then 'connector_artifact_generation_allowed'
        when gp.generation_status = 'gate_reassessment_required' then 'gate_reassessment_required'
        when bg.blocking_gate is not null then 'blocked_by_gate'
        when gp.generation_status = 'ready' then 'connector_generation_ready'
        else 'candidate_review'
    end as current_stage,
    case
        when c.status = 'active_controlled' then 'Monitor existing controlled source'
        when br.build_status = 'build_approval_required' then 'Review and approve connector build request'
        when br.build_status = 'artifact_generation_allowed' then 'Generate connector artifacts under approval gate'
        when gp.generation_status = 'gate_reassessment_required' then 'Rerun employer-origin gate reassessment'
        when bg.blocking_gate is not null then 'Resolve blocking gate: ' || bg.blocking_gate
        when gp.generation_status = 'ready' then 'Review connector generation plan'
        else 'Continue candidate review'
    end as recommended_next_action,
    coalesce(br.build_next_command, gp.generation_next_command) as debug_next_command,
    greatest(
        c.updated_at,
        coalesce(gp.generation_updated_at, c.updated_at),
        coalesce(br.build_updated_at, c.updated_at),
        coalesce(ts.latest_search_term_suggestion_at, c.updated_at),
        coalesce(fp.fn_snapshot_created_at, c.updated_at)
    ) as last_signal_at,
    c.created_at,
    c.updated_at
from employer_origin_source_candidates c
left join gate_summary gs on gs.candidate_id = c.id
left join blocking_gate bg on bg.candidate_id = c.id
left join latest_fn_pressure fp on fp.candidate_id = c.id
left join latest_generation_plan gp on gp.candidate_id = c.id
left join latest_build_request br on br.candidate_id = c.id
left join term_suggestions ts on ts.candidate_id = c.id;

create or replace view gold_market_coverage_summary as
with candidates as (
    select * from gold_candidate_lifecycle_status
),
latest_novelty as (
    select distinct on (source_name, coalesce(search_profile_name, ''), coalesce(search_term, ''))
        id,
        source_name,
        search_profile_name,
        search_term,
        evidence_count,
        distinct_company_count,
        unregistered_company_count,
        known_candidate_company_count,
        newly_observed_company_count,
        repeated_observed_company_count,
        reassessment_company_count,
        newly_observed_term_count,
        repeated_observed_term_count,
        novelty_score,
        saturation_level,
        recommended_action,
        reason,
        created_at
    from aggregator_novelty_snapshots
    order by source_name, coalesce(search_profile_name, ''), coalesce(search_term, ''), created_at desc, id desc
)
select
    now() as generated_at,
    count(*)::integer as employer_origin_candidate_count,
    count(*) filter (where candidate_status = 'active_controlled')::integer as active_origin_connector_count,
    count(*) filter (where candidate_status not in ('active_controlled', 'disabled', 'deprecated', 'abort_documented'))::integer as open_candidate_count,
    count(*) filter (where current_stage = 'blocked_by_gate')::integer as blocked_candidate_count,
    count(*) filter (where current_stage = 'gate_reassessment_required')::integer as gate_reassessment_required_count,
    count(*) filter (where current_stage = 'build_approval_required')::integer as build_approval_required_count,
    count(*) filter (where current_stage = 'connector_artifact_generation_allowed')::integer as connector_artifact_generation_allowed_count,
    count(*) filter (where fn_pressure_level in ('high', 'critical'))::integer as high_fn_pressure_candidate_count,
    count(*) filter (where fn_pressure_level = 'critical')::integer as critical_fn_pressure_candidate_count,
    coalesce(sum(open_search_term_suggestion_count), 0)::integer as open_search_term_suggestion_count,
    (select count(*)::integer from company_vocabulary_observations where created_at >= now() - interval '7 days') as recent_company_vocabulary_observation_count,
    (select count(*)::integer from aggregator_novelty_items where created_at >= now() - interval '7 days' and item_type = 'company' and novelty_state = 'unregistered_company') as recent_unregistered_company_observation_count,
    (select count(*)::integer from aggregator_novelty_items where created_at >= now() - interval '7 days' and item_type = 'term' and novelty_state = 'new_vocabulary_term') as recent_new_vocabulary_term_observation_count,
    (select count(*)::integer from latest_novelty where saturation_level in ('saturating', 'saturated')) as saturated_scope_count,
    (select count(*)::integer from latest_novelty where recommended_action in ('continue_bounded_exploration', 'review_newly_observed_companies', 'review_unregistered_company_backlog', 'rerun_gate_reassessment_for_known_candidates')) as actionable_novelty_scope_count,
    (select max(created_at) from latest_novelty) as latest_aggregator_novelty_snapshot_at
from candidates;

create or replace view gold_approval_queue as
select
    'connector_build'::text as approval_type,
    c.candidate_id,
    c.company_key,
    c.display_company_name,
    c.source_name_candidate,
    c.current_stage,
    c.fn_pressure_level,
    c.fn_pressure_reason as approval_reason,
    c.build_status as approval_status,
    c.build_recommendation as recommendation,
    c.build_mode,
    c.connector_module_path,
    c.connector_test_path,
    c.connector_docs_path,
    c.debug_next_command,
    c.last_signal_at
from gold_candidate_lifecycle_status c
where c.build_status in ('build_approval_required', 'artifact_generation_allowed')
union all
select
    'gate_reassessment'::text as approval_type,
    c.candidate_id,
    c.company_key,
    c.display_company_name,
    c.source_name_candidate,
    c.current_stage,
    c.fn_pressure_level,
    c.blocker_reason as approval_reason,
    c.generation_status as approval_status,
    c.generation_recommendation as recommendation,
    null::text as build_mode,
    c.connector_module_path,
    c.connector_test_path,
    c.connector_docs_path,
    c.debug_next_command,
    c.last_signal_at
from gold_candidate_lifecycle_status c
where c.current_stage = 'gate_reassessment_required';

create or replace view gold_source_health_summary as
select
    source_name_candidate as source_name,
    source_family_candidate as source_family,
    source_type_candidate as source_type,
    source_role,
    count(*)::integer as candidate_count,
    count(*) filter (where candidate_status = 'active_controlled')::integer as active_controlled_count,
    count(*) filter (where current_stage = 'blocked_by_gate')::integer as blocked_candidate_count,
    count(*) filter (where current_stage = 'build_approval_required')::integer as build_approval_required_count,
    count(*) filter (where fn_pressure_level in ('high', 'critical'))::integer as high_fn_pressure_count,
    case
        when count(*) filter (where fn_pressure_level = 'critical') > 0 then 'attention_required'
        when count(*) filter (where current_stage in ('blocked_by_gate', 'build_approval_required', 'gate_reassessment_required')) > 0 then 'review_required'
        when count(*) filter (where candidate_status = 'active_controlled') > 0 then 'controlled_active'
        else 'candidate_monitoring'
    end as health_status,
    max(last_signal_at) as last_signal_at,
    string_agg(distinct blocking_gate, ', ' order by blocking_gate) filter (where blocking_gate is not null) as blocking_gates
from gold_candidate_lifecycle_status
group by source_name_candidate, source_family_candidate, source_type_candidate, source_role;
