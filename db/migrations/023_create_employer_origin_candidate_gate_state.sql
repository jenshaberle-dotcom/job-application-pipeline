-- S2R DB-backed employer-origin candidate gate-state model.
--
-- Purpose:
--   Store source-candidate and gate-review state in PostgreSQL so future
--   connector-building workflows and agents do not depend on CSV/Excel/export
--   files as hidden process inputs.
--
-- Boundary:
--   This migration creates review-state tables only. It does not activate any
--   source, run any connector, approve Bronze persistence or execute any
--   destructive operation.

create table if not exists employer_origin_source_candidates (
    id bigint generated always as identity primary key,
    company_key text not null,
    company_name text not null,
    candidate_url text not null,
    source_name_candidate text not null,
    source_family_candidate text not null,
    source_target_candidate text,
    source_type_candidate text not null default 'employer_origin_career_site',
    status text not null default 'candidate',
    risk_level text not null default 'unknown',
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint employer_origin_source_candidates_unique_source
        unique (company_key, candidate_url),
    constraint employer_origin_source_candidates_status_check
        check (status in (
            'candidate',
            'discovery',
            'deferred',
            'manual_review_required',
            'connector_candidate',
            'active_controlled',
            'watchlist',
            'degraded',
            'deprecated',
            'disabled',
            'abort_documented'
        )),
    constraint employer_origin_source_candidates_risk_level_check
        check (risk_level in (
            'unknown',
            'low',
            'medium',
            'high',
            'blocked'
        )),
    constraint employer_origin_source_candidates_source_type_check
        check (source_type_candidate in (
            'employer_origin_career_site',
            'employer_origin_ats_backed_career_site'
        ))
);

create index if not exists employer_origin_source_candidates_status_idx
    on employer_origin_source_candidates (status);

create index if not exists employer_origin_source_candidates_company_key_idx
    on employer_origin_source_candidates (company_key);

create table if not exists employer_origin_candidate_gate_reviews (
    id bigint generated always as identity primary key,
    candidate_id bigint not null
        references employer_origin_source_candidates (id)
        on delete cascade,
    gate_name text not null,
    gate_order integer not null,
    gate_status text not null default 'not_started',
    decision text not null default 'defer',
    is_hard_gate boolean not null default true,
    stop_reason text,
    evidence jsonb not null default '{}'::jsonb,
    reviewed_at timestamptz,
    reviewed_by text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint employer_origin_candidate_gate_reviews_unique_gate
        unique (candidate_id, gate_name),
    constraint employer_origin_candidate_gate_reviews_gate_status_check
        check (gate_status in (
            'not_started',
            'passed',
            'failed',
            'deferred',
            'manual_review_required',
            'skipped'
        )),
    constraint employer_origin_candidate_gate_reviews_decision_check
        check (decision in (
            'continue',
            'defer',
            'manual_review_required',
            'abort_documented',
            'build_connector_candidate',
            'activate_controlled',
            'disable_or_deprecate'
        )),
    constraint employer_origin_candidate_gate_reviews_stop_reason_check
        check (
            gate_status not in ('failed', 'deferred', 'manual_review_required')
            or stop_reason is not null
        )
);

create index if not exists employer_origin_candidate_gate_reviews_candidate_idx
    on employer_origin_candidate_gate_reviews (candidate_id, gate_order);

create index if not exists employer_origin_candidate_gate_reviews_status_idx
    on employer_origin_candidate_gate_reviews (gate_status);

create table if not exists employer_origin_candidate_gate_events (
    id bigint generated always as identity primary key,
    candidate_id bigint not null
        references employer_origin_source_candidates (id)
        on delete cascade,
    gate_review_id bigint
        references employer_origin_candidate_gate_reviews (id)
        on delete set null,
    event_type text not null,
    previous_state jsonb,
    new_state jsonb not null,
    event_reason text,
    created_at timestamptz not null default now(),
    created_by text,
    constraint employer_origin_candidate_gate_events_event_type_check
        check (event_type in (
            'candidate_created',
            'gate_initialized',
            'gate_updated',
            'candidate_status_updated'
        ))
);

create index if not exists employer_origin_candidate_gate_events_candidate_idx
    on employer_origin_candidate_gate_events (candidate_id, created_at desc);
