-- S7J Candidate Promotion Gate
--
-- Turns candidate-expansion review evidence into an explicit promotion review.
-- Candidate creation remains gated and does not register connectors, activate
-- sources, write Bronze data or change scheduler state.
--
-- Candidate URLs become nullable because market-observed companies can be
-- valid discovery candidates before a safe origin URL has been selected by the
-- Origin Source Discovery Gate. A partial unique index prevents duplicate
-- pending discovery candidates per company.

ALTER TABLE employer_origin_source_candidates
    ALTER COLUMN candidate_url DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_employer_origin_candidates_pending_company
    ON employer_origin_source_candidates (company_key)
    WHERE candidate_url IS NULL;

CREATE TABLE IF NOT EXISTS candidate_promotion_reviews (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    candidate_expansion_review_id bigint NOT NULL
        REFERENCES candidate_expansion_reviews(id) ON DELETE CASCADE,
    reviewed_by text NOT NULL DEFAULT 'agent',
    promotion_mode text NOT NULL DEFAULT 'candidate_expansion_promotion',
    item_count integer NOT NULL DEFAULT 0,
    promotion_recommended_count integer NOT NULL DEFAULT 0,
    manual_review_count integer NOT NULL DEFAULT 0,
    deferred_count integer NOT NULL DEFAULT 0,
    rejected_count integer NOT NULL DEFAULT 0,
    skipped_existing_count integer NOT NULL DEFAULT 0,
    created_candidate_count integer NOT NULL DEFAULT 0,
    boundary jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_candidate_promotion_review_counts CHECK (
        item_count >= 0
        AND promotion_recommended_count >= 0
        AND manual_review_count >= 0
        AND deferred_count >= 0
        AND rejected_count >= 0
        AND skipped_existing_count >= 0
        AND created_candidate_count >= 0
    )
);

CREATE INDEX IF NOT EXISTS idx_candidate_promotion_reviews_created
    ON candidate_promotion_reviews (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidate_promotion_reviews_expansion
    ON candidate_promotion_reviews (candidate_expansion_review_id, created_at DESC);

CREATE TABLE IF NOT EXISTS candidate_promotion_review_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    promotion_review_id bigint NOT NULL
        REFERENCES candidate_promotion_reviews(id) ON DELETE CASCADE,
    candidate_expansion_item_id bigint NOT NULL
        REFERENCES candidate_expansion_review_items(id) ON DELETE CASCADE,
    candidate_expansion_review_id bigint NOT NULL
        REFERENCES candidate_expansion_reviews(id) ON DELETE CASCADE,
    company_key text NOT NULL,
    company_name text NOT NULL,
    source_name text NOT NULL,
    source_decision text NOT NULL,
    promotion_decision text NOT NULL,
    priority integer NOT NULL DEFAULT 0,
    evidence_count integer NOT NULL DEFAULT 0,
    source_name_candidate text NOT NULL,
    source_family_candidate text NOT NULL,
    source_target_candidate text,
    source_type_candidate text NOT NULL DEFAULT 'employer_origin_career_site',
    candidate_url text,
    risk_level text NOT NULL DEFAULT 'unknown',
    reason text NOT NULL,
    recommended_next_action text NOT NULL,
    created_candidate_id bigint
        REFERENCES employer_origin_source_candidates(id) ON DELETE SET NULL,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_candidate_promotion_item_counts CHECK (evidence_count >= 0),
    CONSTRAINT chk_candidate_promotion_item_decision CHECK (
        promotion_decision = ANY (ARRAY[
            'promotion_recommended'::text,
            'promotion_manual_review_required'::text,
            'promotion_deferred'::text,
            'promotion_rejected_noise'::text,
            'promotion_skipped_existing'::text
        ])
    ),
    CONSTRAINT chk_candidate_promotion_item_risk CHECK (
        risk_level = ANY (ARRAY['unknown'::text, 'low'::text, 'medium'::text, 'high'::text, 'blocked'::text])
    )
);

CREATE INDEX IF NOT EXISTS idx_candidate_promotion_items_review
    ON candidate_promotion_review_items (promotion_review_id);

CREATE INDEX IF NOT EXISTS idx_candidate_promotion_items_company
    ON candidate_promotion_review_items (company_key, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_candidate_promotion_items_decision_priority
    ON candidate_promotion_review_items (promotion_decision, priority DESC, evidence_count DESC);
