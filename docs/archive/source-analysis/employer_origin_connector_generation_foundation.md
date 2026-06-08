# Employer-Origin Connector Generation Foundation

## Status

Implemented as S6A foundation.

## Purpose

S6A turns the existing employer-origin gate evidence into an explicit, DB-backed connector-generation plan.

The goal is not to build more one-off connector scripts manually. The goal is a controlled path from a discovered company/source candidate to a bounded connector implementation plan that can later be reviewed, generated, validated and registered without hidden local handoffs.

## Strategic Reason

The current Search Intelligence bottleneck is not the ability to compute more scores. The bottleneck is Ground Truth.

Capability Gap and Search-Term Value become more useful when the project confirms more real employer-origin jobs. Employer-origin sources provide that confirmation because they represent source-owner evidence instead of aggregator-only market hints.

## Flow

```text
Discovery Candidate
↓
Source Analysis
↓
Connector Feasibility
↓
Connector Recommendation
↓
Build Plan / Review Artifact
↓
Connector Artifact Dry Run
↓
Validation / Approval / Registration Gates
```

## What S6A Adds

S6A adds:

- `employer_origin_connector_generation_plans`
- `src/search_intelligence/employer_origin_connector_generation.py`
- `scripts/run_employer_origin_connector_generation_foundation_agent.py`

The foundation reads existing DB-backed candidate and gate state, evaluates whether connector generation is justified and stores a reviewable generation plan when explicitly run with `--write`.

## Boundaries

S6A does not:

- create an auto-PR
- activate a source
- write Bronze records
- approve recurring ingestion
- change scheduler behavior
- use CSV, Excel or generated export artifacts as pipeline inputs
- replace the existing validation, final approval or registration gates

Human-readable JSON/Markdown reports may be written under `exports/`, but they are review outputs only. PostgreSQL remains the process state.

## Learning-Triggered Gate Reassessment

S6A must not treat learning and connector generation as isolated tools. Search Intelligence learning is a feedback signal for employer-origin gate state.

When false-negative / market-coverage evidence increases for an unresolved employer-origin candidate, the learning layer writes an open reassessment item. S6A reads that reassessment signal before recommending connector generation, but only treats it as blocking when the learning item is newer than the latest recorded gate review.

If such a signal is open, S6A does not build or generate connector artifacts. Instead it routes the candidate back into employer-origin gate reassessment, usually through the bounded agent chain / detail-evidence repair path.

This distinction is intentional:

```text
Market-learning evidence increased
→ search terms / vocabulary / false-negative risk are updated
→ candidate gate state may be stale if the learning item is newer than the latest gate review
→ rerun bounded gate reassessment
→ only then reconsider connector generation
```

Learning evidence can therefore raise the urgency and priority of a candidate, but it cannot bypass source-analysis, detail-evidence, uniqueness or connector-candidate gates.

For example, a company may have `false_negative_risk_level = critical` because it appears repeatedly in aggregator evidence while its employer-origin source remains unresolved. That is not the same as a critical technical/source risk. It means the candidate is important for market coverage and should be reassessed before connector generation remains blocked or proceeds.

## Relationship to Earlier Employer-Origin Agents

Earlier S2/S4 agents already cover the lower-level gate and artifact mechanics:

- candidate gates
- detail evidence repair
- connector candidate specification
- build-readiness checks
- connector artifact generation
- connector validation
- final approval
- registration execution planning

S6A sits above these mechanics as a connector-generation planning foundation. It makes the path explicit and reviewable before artifact generation happens.

## Example

Preview only:

```bash
python -m scripts.run_employer_origin_connector_generation_foundation_agent \
  --company-key hdi \
  --reviewed-by jens \
  --report
```

Persist the DB-backed plan after review:

```bash
python -m scripts.run_employer_origin_connector_generation_foundation_agent \
  --company-key hdi \
  --reviewed-by jens \
  --write \
  --report
```

Possible next command produced by the plan:

```bash
python -m scripts.run_employer_origin_connector_artifact_generator \
  --company-key hdi \
  --dry-run
```

If connector artifact files already exist, the plan recommends validation instead of blind regeneration.

## Interpretation

A `ready / prepare_connector_artifact_dry_run` generation plan means:

- required DB-backed gates are passed
- connector candidate evidence exists
- concrete detail URLs exist
- a bounded artifact dry run is justified

It does not mean:

- the connector is production-ready
- the source is active
- Bronze persistence is approved
- recurring ingestion is approved
- registration is approved

## Search Intelligence Link

S6A closes the loop from market understanding back into Ground Truth expansion. The loop is not one-way: learned evidence can send a candidate back to gate reassessment before connector generation continues.

```text
Exploration Evidence
→ Company Vocabulary
→ Candidate Intelligence
→ Search-Term Value
→ Capability Gap
→ Employer-Origin Connector Generation
→ Confirmed Origin Jobs
→ Better Market Evidence
```

This keeps False Negative work measurable as market-coverage improvement instead of pretending that unknown missed jobs can be measured directly.
