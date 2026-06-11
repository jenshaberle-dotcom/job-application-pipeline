# QUALITY-001 Search Intelligence Quality & Recall Foundation

QUALITY-001 is a read-only quality layer for Search Intelligence. It bundles the
next parallelizable diagnostic work after the standard workflow foundation and
after BA remote monitoring, market-sensor funnel work, and StepStone discovery
cycle work are present.

## Scope

QUALITY-001 combines four diagnostic subitems:

- `SENSOR-001I` — BA Remote Effectiveness Review
- `MARKET-002A` — Promotion Funnel Quality
- `STEPSTONE-002A` — Discovery Novelty & Saturation Review
- `ASSUMPTION-001A` — Assumption Inventory Bootstrap

The intent is to answer whether Search Intelligence is producing useful recall
signal or merely producing activity/volume.

## Safety boundary

QUALITY-001 is diagnostic only:

- no external requests
- no database writes
- no candidate or gate mutation
- no connector generation or activation
- no Bronze/Silver/Gold mutation
- no scheduler mutation
- no CSV/export-as-input workflow

QUALITY-001 output is not gate truth. It is a review and prioritization signal
that can point to follow-up work, but concrete candidate/source decisions still
need their normal evidence and gate paths.

## SENSOR-001I: BA Remote Effectiveness Review

The BA remote/nationwide review interprets an existing `SENSOR-001H` report. It
classifies the observed run state into levels such as:

- `awaiting_first_run`
- `blocked_by_failed_runs`
- `duplicate_dominated`
- `low_incremental_yield`
- `observed_incremental_yield`

The review focuses on inserted share, duplicate share, failed runs, observed
terms, and silent terms. It deliberately does not run ingestion.

## MARKET-002A: Promotion Funnel Quality

The market funnel review uses market-sensor review items and employer-origin
connector candidates. It highlights whether observed companies have reached the
candidate funnel and whether high-priority or `create_candidate_recommended`
companies are stuck before candidate creation.

This is primarily a false-negative control: market observations should not be
silently lost before reaching origin-candidate review.

## STEPSTONE-002A: Discovery Novelty & Saturation Review

The StepStone novelty review interprets existing discovery assessments. It
tracks:

- new-company share
- known-company share
- relevance share
- drift share
- saturation level
- recommended interval

This keeps known-company suppression honest: suppression may help reveal new
companies, but it must not silently become a permanent false-negative mechanism.

## ASSUMPTION-001A: Assumption Inventory Bootstrap

QUALITY-001 starts a small assumption inventory for the current Search
Intelligence loop:

- BA remote/nationwide incremental value
- StepStone suppression and novelty
- market-promotion recall
- the boundary that QUALITY-001 metrics are diagnostic and not gate truth

Each assumption records risk type, decision scope, required evidence,
validation method, review status, and recheck trigger.

## Command

Create a bootstrap report:

```bash
python scripts/run_quality001_search_intelligence_quality_review.py
```

Create a report with the latest approved SENSOR-001H export:

```bash
python scripts/run_quality001_search_intelligence_quality_review.py \
  --sensor001h-json exports/<sensor001h_report>.json
```

The command writes JSON and Markdown reports to `exports/`.

## Follow-up boundary

Likely follow-ups after QUALITY-001 are:

- review BA duplicate provenance and company novelty before broadening BA remote
- inspect market promotion gaps before adding new sensors
- repair or reassess StepStone discovery loop if novelty collapses
- only then consider deeper Türsteher, MARKET-003, or EO-003 changes
