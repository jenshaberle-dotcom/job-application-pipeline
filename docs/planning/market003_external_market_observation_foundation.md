# MARKET-003 External Market Observation Foundation

## Purpose

MARKET-003 models manually observed market signals as explicit learning input.
Dry-run planning and review are read-only. Persistence is available only via an
explicit `--write` flag and is limited to the existing `market_evidence` table.
Examples include LinkedIn sightings, recruiter notes, job fairs, personal
research, manually checked aggregator hits, or a company career-page sighting.

The intent is recall and blind-spot measurement, not job ingestion and not gate
truth. A manual observation may later feed candidate-expansion review, but it
must remain permanently recognizable as `manual_market_observation`.

## Scope

This block adds a structured MARKET-003 model and CLI around `market_evidence`:

- `ManualMarketObservationInput`
- `ManualMarketObservationPlan`
- `ManualMarketObservationReview`
- dry-run-first CLI for one observation
- explicit-write-only persistence into `market_evidence`
- read-only database review mode for existing manual observations, producing only export reports
- explicit safety boundary
- tests for model and CLI contract

## Boundary

MARKET-003 is **not purely read-only** when `--write` is used. The write boundary is intentionally narrow:

- default mode is dry-run
- `--write` is required for persistence
- persistence writes only `evidence_kind = manual_market_observation` rows to `market_evidence`
- the signal remains learning input, not gate truth

MARKET-003 does not:

- ingest jobs
- write Bronze, Silver or Gold job state
- create employer-origin candidates
- mutate gates
- activate sources
- build or register connectors
- change scheduler state
- use CSV or exports as pipeline input

## Operational use

Dry-run first:

```bash
python scripts/run_market003_external_market_observation.py \
  --company-name "Bahlsen GmbH" \
  --title "Data Engineer" \
  --observation-channel linkedin \
  --evidence-url "https://example.invalid/job" \
  --search-term "data engineer" \
  --remote-signal hybrid \
  --relevance-signal strong \
  --note "Manual LinkedIn reality-check hit"
```

Persist only after review:

```bash
python scripts/run_market003_external_market_observation.py \
  --company-name "Bahlsen GmbH" \
  --title "Data Engineer" \
  --observation-channel linkedin \
  --relevance-signal strong \
  --write
```

Review existing manual observations. This reads the database and writes only JSON/Markdown reports under `exports/`:

```bash
python scripts/run_market003_external_market_observation.py --review-only --days 90
```

## Relation to QUALITY-001

QUALITY-001 created the diagnostic layer for Search Intelligence quality and
assumption visibility. MARKET-003 supplies an explicit manual observation input
stream so external market reality checks do not remain hidden in chat, memory,
screenshots or ad hoc notes.

## Next step

After enough manual observations exist, run candidate-expansion review without
automatic promotion. Promotion remains a separate gated step.
