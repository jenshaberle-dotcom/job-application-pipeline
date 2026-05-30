# Aggregator Discovery Feedback Loop

## Status

Implemented as S4F review-state foundation.

## Purpose

StepStone is useful as a bounded commercial aggregator and company-discovery signal.
It should not become a broad crawl, a canonical job source or a repeated trigger for
already known employer-origin candidates.

This feedback loop keeps those responsibilities separate:

```text
StepStone/Silver company signal
  -> unknown employer
      -> keep for new candidate discovery review
  -> known employer-origin candidate
      -> suppress from aggregator discovery
      -> optionally hand off to employer-origin recheck if policy allows
  -> active controlled employer-origin source
      -> suppress from discovery and monitor through source lifecycle tracking
  -> hard-stop candidate
      -> suppress and preserve hard-stop state
```

## Implemented Components

S4F adds a DB-backed review-state layer for suppression decisions:

- `db/migrations/025_create_aggregator_discovery_suppression_snapshots.sql`
- `scripts/aggregator_discovery_policy.py`
- `scripts/run_aggregator_discovery_suppression_agent.py`
- `tests/test_aggregator_discovery_policy.py`
- `tests/test_aggregator_discovery_suppression_agent.py`
- `tests/test_aggregator_discovery_suppression_migration.py`

The agent reads:

- known employer-origin candidates from `employer_origin_source_candidates`
- latest gate state from `employer_origin_candidate_gate_reviews`
- aggregator company signals from `silver_jobs`

The default source remains:

```text
stepstone
```

## Boundary

The agent does not:

- call StepStone or any other external site
- fetch detail pages
- paginate
- write Bronze rows
- activate sources
- register connectors
- modify scheduler behavior
- use CSV/Excel/export artifacts as process inputs

Snapshot persistence is optional review-state only.

```bash
python -m scripts.run_aggregator_discovery_suppression_agent --limit 50
```

After manual inspection, a review-state snapshot can be persisted:

```bash
python -m scripts.run_aggregator_discovery_suppression_agent \
  --limit 50 \
  --write-snapshot \
  --reviewed-by manual
```

This writes only the displayed/selected review set. Omit `--limit` for a full-source snapshot.

This writes only to:

- `aggregator_discovery_suppression_batches`
- `aggregator_discovery_suppression_items`

It does not approve activation or Bronze persistence.

## Handoff Actions

Each suppression decision has a handoff action:

| Handoff action | Meaning |
|---|---|
| `keep_for_new_candidate_discovery` | Company is not known yet and can become a new candidate-review input. |
| `suppress_from_aggregator_discovery` | Company is already known and should not create another discovery candidate. |
| `queue_employer_origin_recheck` | Company is known, inactive and due for policy-allowed employer-origin lifecycle recheck. |

The handoff action is advisory review state. It does not enqueue or execute work by itself.

## Why this matters for StepStone

The recent StepStone policy change means the project must not interpret repeated
StepStone visibility as permission to expand StepStone acquisition or to rediscover
the same companies over and over.

StepStone remains valuable when it reveals new companies, vocabulary or market
signals. Once a company is already represented in the employer-origin candidate
model, the employer-origin lifecycle owns the next decision.

This keeps StepStone defensive and useful without turning it into an aggregator loop.

## Feed-Forward StepStone Filtering

The suppression snapshot alone is not enough for the intended StepStone workflow.
The operational expectation is feed-forward filtering:

```text
known employer-origin candidates in DB
  -> normalized company exclusion keys
  -> next bounded StepStone ingestion run
  -> suppress matching result cards before Bronze persistence
  -> persist only unknown-company StepStone cards, or persist nothing if the page is fully suppressed
```

The implementation therefore also adds an ingestion-time filter for `stepstone`.
The filter runs after the single bounded StepStone page has been fetched and parsed,
but before `raw_jobs` and `job_observations` are written. This is deliberately not a
server-side StepStone query trick. Unless a stable, documented StepStone exclusion
parameter is proven later, the project only performs local suppression against the
one fetched result-card page.

Consequences:

- known employer-origin candidates do not consume new Bronze/discovery rows
- the bounded 25-result StepStone page can become smaller or empty after suppression
- the connector still does not paginate or try to refill suppressed results from later pages
- the suppression source of truth is the DB-backed employer-origin candidate model
- CSV/Excel/export artifacts are not used as filter input

This keeps StepStone useful as a bounded discovery signal while avoiding repeated
rediscovery of HDI, HDI group variants, Finanz Informatik or other already-known candidates.
