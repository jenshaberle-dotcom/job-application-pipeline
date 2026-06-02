-- S7F Search Intelligence Nightly Orchestrator Foundation
--
-- Purpose:
--   Store explicit Search Intelligence orchestration run reviews and step-level
--   outcomes without mutating sources, search profiles, Bronze/Silver data,
--   connector registration or scheduler state.
--
-- Boundary:
--   This is an audit/control-plane model. The orchestrator may write its own
--   run report when explicitly executed with --write, but it must not perform
--   irreversible pipeline actions.

create table if not exists search_intelligence_orchestrator_runs (
    id bigserial primary key,
    cycle_name text not null,
    run_mode text not null default 'dry_run',
    requested_by text not null,
    status text not null,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    summary jsonb not null default '{}'::jsonb,
    guardrails jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint chk_search_intelligence_orchestrator_run_mode
        check (run_mode in ('dry_run', 'write_audit_only')),
    constraint chk_search_intelligence_orchestrator_run_status
        check (status in ('completed', 'completed_with_actions', 'blocked', 'failed'))
);

create table if not exists search_intelligence_orchestrator_steps (
    id bigserial primary key,
    run_id bigint not null references search_intelligence_orchestrator_runs(id) on delete cascade,
    step_order integer not null,
    step_name text not null,
    step_status text not null,
    action_mode text not null,
    recommendation text not null,
    reason text,
    metrics jsonb not null default '{}'::jsonb,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    constraint chk_search_intelligence_orchestrator_step_status
        check (step_status in ('ok', 'attention_required', 'blocked', 'not_ready', 'deferred')),
    constraint chk_search_intelligence_orchestrator_action_mode
        check (action_mode in ('observe', 'recommend', 'queue_review', 'manual_approval_required', 'defer'))
);

create unique index if not exists idx_search_intelligence_orchestrator_steps_unique_order
    on search_intelligence_orchestrator_steps(run_id, step_order);

create index if not exists idx_search_intelligence_orchestrator_runs_created_at
    on search_intelligence_orchestrator_runs(created_at desc);

create index if not exists idx_search_intelligence_orchestrator_steps_run
    on search_intelligence_orchestrator_steps(run_id, step_order);
