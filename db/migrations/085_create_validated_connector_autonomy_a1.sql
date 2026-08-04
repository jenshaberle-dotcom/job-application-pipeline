-- CONNECTOR-AUTONOMY-A1-001
-- Standing operator authorization for validated connector registration and
-- separately gated controlled activation. Recurring execution remains disabled.

CREATE TABLE IF NOT EXISTS connector_autonomy_policies (
    policy_key TEXT PRIMARY KEY,
    autonomy_level TEXT NOT NULL,
    status TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    standing_authorization BOOLEAN NOT NULL,
    require_connector_validation BOOLEAN NOT NULL,
    require_exact_activation_readiness BOOLEAN NOT NULL,
    allowed_activation_readiness TEXT NOT NULL,
    allow_connector_registration BOOLEAN NOT NULL,
    allow_controlled_source_activation BOOLEAN NOT NULL,
    allow_bounded_first_ingestion BOOLEAN NOT NULL,
    allow_recurring_ingestion BOOLEAN NOT NULL,
    allow_scheduler_mutation BOOLEAN NOT NULL,
    allow_provider_requests BOOLEAN NOT NULL,
    allow_ranking_mutation BOOLEAN NOT NULL,
    allow_application_actions BOOLEAN NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMPTZ,
    paused_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_connector_autonomy_policy_key
        CHECK (policy_key = 'validated_connector_a1'),
    CONSTRAINT chk_connector_autonomy_level
        CHECK (autonomy_level = 'a1_validated_connector_controlled_activation'),
    CONSTRAINT chk_connector_autonomy_status
        CHECK (status IN ('approved', 'paused', 'revoked')),
    CONSTRAINT chk_connector_autonomy_readiness
        CHECK (allowed_activation_readiness = 'activation_readiness_supported'),
    CONSTRAINT chk_connector_autonomy_approval CHECK (
        status <> 'approved'
        OR (standing_authorization AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
    ),
    CONSTRAINT chk_connector_autonomy_a1_bounds CHECK (
        require_connector_validation
        AND require_exact_activation_readiness
        AND allow_connector_registration
        AND allow_controlled_source_activation
        AND allow_bounded_first_ingestion
        AND NOT allow_recurring_ingestion
        AND NOT allow_scheduler_mutation
        AND NOT allow_provider_requests
        AND NOT allow_ranking_mutation
        AND NOT allow_application_actions
    )
);

INSERT INTO connector_autonomy_policies (
    policy_key, autonomy_level, status, policy_version,
    standing_authorization, require_connector_validation,
    require_exact_activation_readiness, allowed_activation_readiness,
    allow_connector_registration, allow_controlled_source_activation,
    allow_bounded_first_ingestion, allow_recurring_ingestion,
    allow_scheduler_mutation, allow_provider_requests,
    allow_ranking_mutation, allow_application_actions,
    approved_by, approved_at
)
VALUES (
    'validated_connector_a1',
    'a1_validated_connector_controlled_activation',
    'approved',
    'connector-autonomy-a1-2026-08-04',
    TRUE, TRUE, TRUE, 'activation_readiness_supported',
    TRUE, TRUE, TRUE, FALSE, FALSE, FALSE, FALSE, FALSE,
    'jens', TIMESTAMPTZ '2026-08-04 20:10:00+02'
)
ON CONFLICT (policy_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS connector_autonomy_authorization_events (
    id BIGSERIAL PRIMARY KEY,
    candidate_id BIGINT REFERENCES employer_origin_source_candidates(id)
        ON DELETE SET NULL,
    source_name_candidate TEXT,
    action TEXT NOT NULL,
    decision TEXT NOT NULL,
    authorization_mode TEXT NOT NULL,
    policy_key TEXT REFERENCES connector_autonomy_policies(policy_key),
    policy_version TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    recorded_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_connector_autonomy_event_action CHECK (
        action IN ('connector_registration', 'controlled_source_activation', 'bounded_first_ingestion')
    ),
    CONSTRAINT chk_connector_autonomy_event_decision CHECK (
        decision IN ('allowed', 'blocked', 'manual_review_required')
    ),
    CONSTRAINT chk_connector_autonomy_event_evidence
        CHECK (jsonb_typeof(evidence) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_connector_autonomy_events_candidate
ON connector_autonomy_authorization_events (candidate_id, created_at DESC);

CREATE OR REPLACE VIEW gold_connector_autonomy_policy AS
SELECT
    p.*,
    CASE
        WHEN status = 'approved'
         AND standing_authorization
         AND require_connector_validation
         AND require_exact_activation_readiness
         AND allowed_activation_readiness = 'activation_readiness_supported'
         AND allow_connector_registration
         AND allow_controlled_source_activation
         AND allow_bounded_first_ingestion
         AND NOT allow_recurring_ingestion
         AND NOT allow_scheduler_mutation
         AND NOT allow_provider_requests
         AND NOT allow_ranking_mutation
         AND NOT allow_application_actions
        THEN 'active_a1_fail_closed'
        ELSE status
    END AS runtime_readiness
FROM connector_autonomy_policies p
WHERE policy_key = 'validated_connector_a1';
