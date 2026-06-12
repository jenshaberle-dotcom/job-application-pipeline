# GENERIC-001 Pipeline Generics Proof Gate

Status: planned gate before production-like candidate throughput  
Scope: Search Intelligence / Candidate Pipeline / Origin Evidence / Connector Readiness / Matching

## Purpose

Before the pipeline processes a larger candidate batch or moves toward a production-like product version, it must prove that the core logic is generic enough across different companies, source patterns and evidence shapes.

The goal is to avoid manually pushing 20+ candidates through a pipeline that only works for a few known examples.

## Placement in the roadmap

GENERIC-001 must run after the controlled evidence/review loop has produced candidate-review decisions and before broad candidate apply, broad wave-search scaling, or a productized TOP5 workflow.

Recommended sequence:

1. EXPAND-003 Candidate Review Delta Report
2. GENERIC-001 Pipeline Generics Proof Gate
3. EXPAND-004 Controlled Candidate Creation Dry-Run
4. Wave Search / Scheduler Intelligence
5. Matching / TOP5 Product MVP

## What must be proven

GENERIC-001 should validate that the pipeline can handle a representative candidate set without company-specific hardcoding.

Required coverage dimensions:

- employer-origin site with clear career domain
- career subdomain such as `career.*` or `karriere.*`
- ATS/provider-backed origin such as Personio, Onlyfy, Workday, Greenhouse, Lever, ZohoRecruit, SmartRecruiters or similar
- acronym / alias-heavy company identity
- company with weak-only aggregator evidence
- company with ambiguous or false-positive identity risk
- company with no actionable evidence
- at least one active/known-good control candidate
- at least one stopped/blocked candidate

## Minimum benchmark set

The benchmark should start small and controlled, not with 20+ unreviewed candidates.

Recommended initial set:

- 8 to 12 candidates
- at least 4 strong candidates
- at least 3 weak/noise candidates
- at least 2 ambiguous identity candidates
- at least 1 known positive control
- at least 1 known negative/blocked control

## Success criteria

A candidate may be considered generically handled when the system can explain:

- which source/evidence type was found
- why it is strong, weak or rejected
- whether identity is reliable or ambiguous
- which next step is allowed
- which next step is explicitly blocked
- whether a human review is required

GENERIC-001 passes only if the benchmark produces stable, explainable outcomes without company-specific patches for individual candidates.

## Required outputs

GENERIC-001 should produce review artifacts, not database mutations:

- JSON benchmark report
- Markdown summary for human review
- candidate-by-candidate decision table
- false-positive / false-negative risk notes
- generic gaps discovered
- follow-up recommendations

## Safety boundary

GENERIC-001 is a proof gate, not an apply step.

It must not:

- create candidates automatically
- write gate decisions
- activate connectors
- mutate Bronze, Silver or Gold
- change scheduler behavior
- perform uncontrolled external requests
- use CSV/Excel/local exports as pipeline inputs

## Relationship to EXPAND-004

EXPAND-004 Controlled Candidate Creation Dry-Run should not become a broad production-like apply flow until GENERIC-001 has shown that candidate evidence, identity and next-step classification are generic enough.

If GENERIC-001 finds gaps, EXPAND-004 may still be built as a dry-run contract, but it must stay explicitly limited to a small reviewed benchmark set.

## Relationship to Wave Search and Scheduler

Wave Search and Scheduler Intelligence may be planned in parallel, but broad wave execution should wait until GENERIC-001 has proven that downstream candidate interpretation is robust enough.

Otherwise the system may discover more candidates than it can safely interpret.

## Relationship to TOP5 Product MVP

The TOP5 product version depends on candidate and job evidence being generic enough.

No TOP5 product claim should be made until the pipeline can show that discovery, evidence, review, candidate creation dry-run and matching logic work across a representative candidate set.
