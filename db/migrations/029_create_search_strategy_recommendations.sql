create table if not exists search_strategy_recommendations (
    id bigserial primary key,
    candidate_id bigint references employer_origin_source_candidates(id),
    company_key text not null,
    source_name_candidate text,
    source_family_candidate text,
    suggested_term text not null,
    recommendation_type text not null,
    recommendation_status text not null default 'pending_review',
    autonomy_level text not null default 'manual_approval_required',
    confidence_score numeric(5,2) not null default 0,
    confidence_level text not null default 'unknown',
    sample_size integer not null default 0,
    success_count integer not null default 0,
    failure_count integer not null default 0,
    noise_count integer not null default 0,
    false_negative_risk_level text,
    false_negative_sighting_count integer not null default 0,
    guardrail_decision text not null,
    guardrail_summary jsonb not null default '{}'::jsonb,
    reason text not null,
    reviewed_by text not null default 'agent',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (company_key, source_family_candidate, suggested_term, recommendation_type)
);

create index if not exists idx_search_strategy_recommendations_status
    on search_strategy_recommendations (recommendation_status, updated_at desc);

create index if not exists idx_search_strategy_recommendations_company
    on search_strategy_recommendations (company_key, updated_at desc);

create index if not exists idx_search_strategy_recommendations_guardrail
    on search_strategy_recommendations (guardrail_decision, updated_at desc);
