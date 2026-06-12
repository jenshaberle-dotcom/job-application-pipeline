# GENERIC-001 Genericity Proof Matrix

Status: planned evidence contract

## Purpose

GENERIC-001 defines how the project proves that the Search Intelligence and
candidate-expansion workflow is generic enough before pushing 20+ candidates
through the pipeline.

The goal is not to make gates weaker. The goal is to know whether the pipeline
can transfer its logic across unfamiliar companies, evidence shapes, and source
patterns without relying on manually favored examples.

## Score model

| Dimension | Meaning | Target for >80 |
| --- | --- | --- |
| Identity transferability | candidate identity can be built without hardcoded company logic | most sampled companies pass |
| Evidence transferability | source/evidence URLs are concrete enough for review | majority ready or explainably stopped |
| Stop quality | stops are precise, reusable, and action-guiding | no vague generic stops |
| Duplicate handling | duplicate/known-company decisions are explainable | no silent suppression |
| Relevance handling | Hannover/remote/role relevance is evidence-backed or unknown | no unvalidated assumptions as truth |
| Origin-source readiness | candidate can move toward employer-origin validation | ready/manual-review split is clear |
| Auditability | recommendation can be reproduced from DB-backed evidence | every decision has provenance |

## Recommended sample structure

Use a mixed sample instead of only known successes:

- known active/positive examples
- blocked examples such as detail-evidence failures
- newly discovered company-name-only candidates
- candidates with weak/ambiguous URLs
- known-company or duplicate-risk examples
- manually observed market signals that are explicitly marked as learning input

## Classification contract

Each sample should receive exactly one primary classification:

- `generic_ready_for_candidate_creation_review`
- `manual_review_required`
- `insufficient_origin_evidence`
- `duplicate_or_known_company_risk`
- `normalization_assumption_required`
- `out_of_scope_or_low_relevance`
- `stop_do_not_create_candidate`

Secondary flags may be added for:

- false-positive risk
- false-negative risk
- compliance/operational risk
- assumption-not-yet-validated
- needs URL discovery rerun
- needs detail-evidence repair

## Decision boundary

GENERIC-001 is a proof and diagnosis layer.

It must not:

- create candidates
- pass gates
- activate sources
- generate connector artifacts
- mutate Bronze/Silver/Gold
- mutate scheduler state

A good genericity result allows the next apply-capable work item to be designed.
It does not itself approve writes.
