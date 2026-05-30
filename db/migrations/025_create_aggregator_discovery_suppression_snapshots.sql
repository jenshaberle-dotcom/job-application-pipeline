-- S4F DB-backed aggregator discovery suppression snapshots.
--
-- Purpose:
--   Persist StepStone/aggregator discovery suppression review state so repeated
--   aggregator sightings of already known employer-origin candidates do not become
--   export-file handoffs or repeated candidate loops.
--
-- Boundary:
--   These tables store review decisions only. They do not activate sources,
--   register connectors, write Bronze rows, schedule ingestion or approve any
--   destructive operation.

create table if not exists aggregator_discovery_suppression_batches (
    id bigint generated always as identity primary key,
    created_at timestamptz not null default now(),
    decision_scope text not null,
    aggregator_sources text[] not null default array[]::text[],
    company_count integer not null default 0,
    suppressed_count integer not null default 0,
    kept_for_discovery_review_count integer not null default 0,
    recheck_eligible_known_candidate_count integer not null default 0,
    reviewed_by text,
    evidence jsonb not null default '{}'::jsonb,
    constraint aggregator_discovery_suppression_batches_scope_check
        check (decision_scope in (
            'stepstone_known_candidate_suppression'
        )),
    constraint aggregator_discovery_suppression_batches_counts_check
        check (
            company_count >= 0
            and suppressed_count >= 0
            and kept_for_discovery_review_count >= 0
            and recheck_eligible_known_candidate_count >= 0
            and company_count = suppressed_count + kept_for_discovery_review_count
            and recheck_eligible_known_candidate_count <= suppressed_count
        )
);

create index if not exists idx_aggregator_discovery_suppression_batches_created_at
    on aggregator_discovery_suppression_batches (created_at desc);

create index if not exists idx_aggregator_discovery_suppression_batches_scope
    on aggregator_discovery_suppression_batches (decision_scope, created_at desc);

create table if not exists aggregator_discovery_suppression_items (
    id bigint generated always as identity primary key,
    batch_id bigint not null
        references aggregator_discovery_suppression_batches (id)
        on delete cascade,
    aggregator_source_name text not null,
    company_name text not null,
    normalized_company_key text not null,
    silver_job_count integer not null default 0,
    first_seen_at timestamptz,
    last_seen_at timestamptz,
    decision text not null,
    handoff_action text not null,
    reason text not null,
    known_candidate_id bigint
        references employer_origin_source_candidates (id)
        on delete set null,
    known_candidate_status text,
    known_candidate_source_name text,
    recheck_eligible boolean not null default false,
    recheck_reason text,
    evidence jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    constraint aggregator_discovery_suppression_items_decision_check
        check (decision in (
            'suppress_known_connector_candidate',
            'suppress_active_connector_candidate',
            'suppress_known_hard_stop_candidate',
            'keep_for_discovery_review'
        )),
    constraint aggregator_discovery_suppression_items_action_check
        check (handoff_action in (
            'suppress_from_aggregator_discovery',
            'queue_employer_origin_recheck',
            'keep_for_new_candidate_discovery'
        )),
    constraint aggregator_discovery_suppression_items_counts_check
        check (silver_job_count >= 0),
    constraint aggregator_discovery_suppression_items_recheck_reason_check
        check (not recheck_eligible or recheck_reason is not null)
);

create index if not exists idx_aggregator_discovery_suppression_items_batch
    on aggregator_discovery_suppression_items (batch_id);

create index if not exists idx_aggregator_discovery_suppression_items_source_company
    on aggregator_discovery_suppression_items (aggregator_source_name, normalized_company_key);

create index if not exists idx_aggregator_discovery_suppression_items_decision
    on aggregator_discovery_suppression_items (decision);

create index if not exists idx_aggregator_discovery_suppression_items_recheck
    on aggregator_discovery_suppression_items (recheck_eligible)
    where recheck_eligible = true;
