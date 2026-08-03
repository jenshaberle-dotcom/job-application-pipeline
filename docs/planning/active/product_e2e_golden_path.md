# Product E2E Generic Discovery-to-Top5 Golden Path

Status: implementation in review  
Risk: R1 read-only evidence audit  
Product authority: PRD company discovery, origin validation and bounded Top-5 serving

## Operator outcome

The first end-to-end product proof is intentionally run across at most five real
cases discovered through heterogeneous inputs:

- an aggregator/company-discovery source such as StepStone;
- the Bundesagentur für Arbeit public job API;
- a manual observation recorded by Jens;
- up to two additional high-priority cases from the current seed pool.

The phrase "Top 5" describes the bounded audit portfolio first. It does not force
five jobs into the Product Top-5 view and does not treat a company as a special
case.

## Generic chain

Every selected case is evaluated with the same stages:

```text
discovery signal
→ normalized employer identity
→ employer-origin candidate
→ validated origin URL
→ relevant origin inventory
→ connector build
→ controlled source activation
→ job ingestion
→ Silver normalization
→ Product V1 assessment
→ Top-5 serving or valid no-qualifier stop
```

Discovery provenance changes only the first-stage evidence:

- StepStone and other aggregators are company-discovery signals;
- Bundesagentur jobs are public job/text signals and must still resolve to an
  employer origin before authoritative Product V1 eligibility;
- manual observations may contain a company, a job URL or an origin hint, but do
  not bypass identity, origin, connector or product gates.

After employer identity is available, source and company names are forbidden as
control-flow conditions. The same downstream state and gate rules apply.

## Portfolio selection

The audit selects at most five deduplicated employers. It first tries to include
one case from each primary discovery class and fills remaining slots by existing
seed priority. There is no company allowlist, company-specific threshold or
employer-specific repair branch.

A missing primary source class is reported as coverage evidence. It is not silently
replaced by a fabricated case.

## Read-only evidence inspected

The runner reuses the current DB-backed origin observation seed pool and joins
available current-truth read models:

- `gold_candidate_lifecycle_status`;
- `employer_origin_candidate_gate_reviews`;
- `gold_connector_build_candidate_queue`;
- `raw_jobs` by exact observed URL where possible;
- `silver_jobs` by normalized employer identity;
- `gold_product_v1_job_readiness`;
- `gold_product_v1_top_jobs`.

Absent relations or evidence fail closed as unknown/missing evidence. The runner
does not infer success from source reachability, connector files or aggregator
listings alone.

## Result classes

Each stage is classified as one of:

- `passed` — evidence proves the stage;
- `valid_stop` — the chain completed correctly but no job qualifies or enters the
  bounded Top-5;
- `missing_evidence` — the next required fact is not established;
- `operator_decision_required` — an explicit product/safety decision is required;
- `capability_gap` — the generic mechanism cannot currently continue;
- `not_reached` — reserved for later extensions when a stage was not evaluated.

Repeated equal gaps across different discovery classes are classified as
`generic_cross_source_gap`. Repetition inside one source class is a
`source_class_gap`; a single unresolved item remains a `case_evidence_gap`.

## Operator decisions

The audit may surface, but never execute, decisions such as:

- selecting among materially non-equivalent origin candidates;
- resolving source-family equivalence or multi-origin coverage;
- approving bounded connector artifact generation;
- approving connector registration and controlled source activation;
- resolving explicitly unknown origin, activity or hard-filter facts.

No decision is requested merely because a case does not reach Top-5. A correctly
blocked, below-threshold or non-qualifying job is a valid product outcome.

## Boundary

The implementation:

- opens a read-only database transaction and rolls it back;
- performs no StepStone, Bundesagentur, Tavily, provider or origin HTTP request;
- creates or changes no candidate, gate, connector, source or scheduler state;
- writes no Bronze, Silver, Gold or Product V1 rows;
- changes no ranking policy and performs no application action;
- writes only JSON/Markdown review artifacts outside pipeline source-of-truth;
- forbids company-specific downstream branching.

## Execution

```bash
python -m scripts.run_product_e2e_golden_path
```

The default selects at most five cases and writes a timestamped JSON/Markdown
artifact under the local Product V1 runtime-artifact directory. Use
`--no-write-artifact` for console-only inspection.

## Exit gate

This slice is complete when:

1. the runner selects a bounded source-diverse portfolio without company rules;
2. all cases use the same stage engine;
3. operator decisions and valid stops are distinct from capability gaps;
4. the current repository suite and Ruff gate pass;
5. the operator runs the audit against the live local DB and reviews the actual
   selected cases and blockers.

The first follow-up must be chosen from observed cross-source evidence. It must not
push one selected employer through the chain with a custom patch.
