-- S7G Gold-backed Orchestrator Attention Views
--
-- Purpose:
--   Surface the latest Search Intelligence orchestrator run and all steps that
--   require attention in stable Gold read models for the Control Center.
--
-- Boundary:
--   Read-only views only. They do not run agents, mutate source/candidate
--   state, register connectors, activate sources, write Bronze records or
--   change scheduler configuration.

create or replace view gold_search_intelligence_orchestrator_latest_run as
select
    r.id as run_id,
    r.cycle_name,
    r.run_mode,
    r.requested_by,
    r.status as run_status,
    r.started_at,
    r.completed_at,
    r.created_at,
    coalesce((r.summary ->> 'step_count')::integer, 0) as step_count,
    coalesce((r.summary ->> 'attention_required_step_count')::integer, 0) as attention_required_step_count,
    coalesce((r.summary ->> 'blocked_step_count')::integer, 0) as blocked_step_count,
    coalesce((r.summary ->> 'approval_queue_count')::integer, 0) as approval_queue_count,
    coalesce((r.summary ->> 'open_candidate_count')::integer, 0) as open_candidate_count,
    coalesce((r.summary ->> 'critical_fn_pressure_candidate_count')::integer, 0) as critical_fn_pressure_candidate_count,
    r.summary,
    r.guardrails
from search_intelligence_orchestrator_runs r
where r.id = (
    select id
    from search_intelligence_orchestrator_runs
    order by created_at desc, id desc
    limit 1
);

create or replace view gold_search_intelligence_orchestrator_attention_steps as
with latest_run as (
    select run_id
    from gold_search_intelligence_orchestrator_latest_run
)
select
    s.id as step_id,
    s.run_id,
    s.step_order,
    s.step_name,
    s.step_status,
    s.action_mode,
    s.recommendation,
    s.reason,
    s.metrics,
    s.started_at,
    s.completed_at,
    s.created_at,
    case
        when s.step_status = 'blocked' then 1
        when s.step_status = 'attention_required' then 2
        when s.step_status = 'not_ready' then 3
        when s.step_status = 'deferred' then 4
        else 9
    end as attention_priority
from search_intelligence_orchestrator_steps s
join latest_run lr on lr.run_id = s.run_id
where s.step_status in ('attention_required', 'blocked', 'not_ready', 'deferred')
order by attention_priority, s.step_order;
