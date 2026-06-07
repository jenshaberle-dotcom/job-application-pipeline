# Pipeline Stopper Reassessment Agent

Status: implementation foundation.

## Purpose

This block adds a dedicated Stopper Reassessment Agent for employer-origin
pipeline blockers. The agent exists because a stopped candidate is not
automatically a correctly rejected candidate. Some stops are valid safety
boundaries, but some are false-negative risks caused by stale evidence,
over-sensitive rules, missing source URLs, access-risk markers in the wrong page
context, or detail-evidence logic that has improved since the stop was recorded.

The agent has one responsibility:

    audit pipeline stoppers and decide whether the stop is valid, stale,
    over-sensitive, or recoverable before the candidate is treated as done.

## Two-stage contract

### Stage 1: Stop-validity audit

Stage 1 is read-only. It inspects candidate status, risk level, latest gate
reviews, stop reasons, and candidate URLs. It classifies each stopper into a
small validity taxonomy, for example:

- `needs_reassessment_likely_over_sensitive`,
- `unconfirmed_stop_recovery_needed`,
- `unconfirmed_detail_evidence_gap`,
- `stop_valid_until_new_evidence`,
- `manual_review_stopper`.

The important output is not only whether a stop exists, but whether the current
stop might itself be a false-negative source.

### Stage 2: Repair plan

Stage 2 is not merely a note for the operator. For recoverable stoppers the
agent emits concrete dry-run and apply commands. Default execution is still
safe: the agent never runs Stage 2 unless explicitly called with write-action
approval.

This avoids the old pattern where a generically difficult candidate had to be
manually debugged through the pipeline in chat. The agent should produce the
next machine-readable repair path itself.

Examples:

- access-risk/bot-defense marker on a candidate with a concrete career URL:
  bounded detail-evidence repair dry-run first, then apply if supported;
- missing or unreachable candidate URL:
  bounded source URL recovery dry-run first, then apply if a safe URL is found;
- detail-evidence gap on a concrete candidate URL:
  bounded detail-evidence repair dry-run first, then apply if supported;
- still ambiguous abort/block:
  canonical chain repair only after explicit operator review.

## Boundary

The default report mode is read-only:

- no candidate status write,
- no candidate URL write,
- no gate review write,
- no evidence write,
- no connector artifact write,
- no connector registration,
- no source activation,
- no scheduler change.

Stage 2 commands are planned commands. Applying them requires explicit operator
choice and the called agent's own dry-run/apply rules.

## Ratiodata lesson

Ratiodata exposed the problem this agent is meant to address. The candidate was
classified as `abort_documented` / `risk_level = blocked` because the source
response contained bot-defense or access-risk markers. A manual review showed
that this can be too broad when markers come from consent, form, footer or
third-party snippets while the job list/detail content is otherwise publicly
available.

The new agent therefore treats access-risk markers on a concrete candidate URL
as a high false-negative-risk stop until reassessed. It does not ignore safety;
it moves the case into a bounded reassessment and repair plan instead of either
blindly rerunning detail repair or permanently accepting the stop.

## Integration with the EO candidate queue

The EO candidate readiness queue now routes blocked operational boundaries and
exhausted detail-evidence stops to:

    python -m scripts.run_pipeline_stop_reassessment_agent \
      --company-key <company_key> \
      --target-location hannover \
      --reviewed-by jens \
      --write-report \
      --print-stage2-command

This prevents normal repair commands from being proposed for blocked candidates
while still avoiding a dead manual-review bucket.

## Recommended smoke commands

Single candidate, Ratiodata-style reassessment:

    python -m scripts.run_pipeline_stop_reassessment_agent \
      --company-key ratiodata \
      --target-location hannover \
      --reviewed-by jens \
      --write-report \
      --print-stage2-command \
      --benchmark-label stopper_reassessment_ratiodata

Portfolio report:

    python -m scripts.run_pipeline_stop_reassessment_agent \
      --target-location hannover \
      --reviewed-by jens \
      --write-report \
      --print-stage2-command \
      --benchmark-label stopper_reassessment_portfolio

## System impact

Discovery: no new source expansion. Source URL recovery can be planned as Stage
2 only for recoverable URL-related stops.

Evidence: no evidence writes in Stage 1. Stage 2 can route to bounded detail
repair using existing dry-run/apply boundaries.

Candidate/Gate: stops become first-class auditable objects instead of final
manual-review dead ends. Stage 1 does not mutate gates.

Connector: no connector files, registration, or activation are produced by the
Stopper Reassessment Agent.

Bronze/Silver/Gold: no job-layer writes in Stage 1.

UI/Observability: the JSON/Markdown report can later feed Operations/Review
Queue views and false-negative monitoring.

## Validation

Targeted validation:

    python -m py_compile \
      scripts/run_pipeline_stop_reassessment_agent.py \
      scripts/run_employer_origin_candidate_queue_agent.py

    python -m pytest \
      tests/test_pipeline_stop_reassessment_agent.py \
      tests/test_employer_origin_candidate_queue_agent.py \
      tests/test_employer_origin_agent_chain.py \
      -q

Before PR:

    python -m pytest -q
    git diff --check
