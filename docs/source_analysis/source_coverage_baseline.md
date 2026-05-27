# Source Coverage Baseline — S1 Controlled Expansion

## Purpose

This document captures the current source-coverage baseline before expanding additional Greenhouse, Personio or employer-origin targets.

The goal is not to rank sources by one headline number. The goal is to make the observed source universe explicit so that later windowed trends, Gold views and dashboard metrics do not confuse source-coverage changes with market movement.

This baseline supports the next phase:

```text
S1 — Controlled Source Coverage Expansion
```

Expansion should add relevant source targets, but it must not repeat the early Greenhouse broad-fetch pattern that created high volume with limited long-term operational value.

## Baseline Timestamp

The baseline reflects the local database state inspected on 2026-05-27 after:

- Historical Burden Analysis
- reviewed test/transient cleanup execution
- source-value window preview implementation
- trend-maturity and source-coverage interpretation boundaries

## Current Active Source Targets

The project currently has 8 active search profiles / source targets.

| Search profile | Source target | Source family | Role in current coverage |
|---|---|---|---|
| `ba_data_engineer_30629_50km` | `bundesagentur_fuer_arbeit` | `bundesagentur_fuer_arbeit` | Official API / stable regional baseline. |
| `greenhouse_stripe` | `greenhouse:stripe` | `greenhouse` | ATS board; valuable learning source but historically burdened by broad legacy data. |
| `stepstone_data_engineer_hannover` | `stepstone` | `stepstone` | Commercial aggregator; intentionally limited acquisition depth. |
| `personio_schluetersche_data_engineer_hannover` | `personio:schluetersche-mediengruppe` | `personio` | Employer-near ATS target. |
| `personio_eraneos_data_engineer_remote` | `personio:eraneos` | `personio` | Employer-near ATS target. |
| `personio_1komma5grad_data_engineer_germany` | `personio:1komma5grad` | `personio` | Employer-near ATS target. |
| `personio_itp_data_engineer_hannover` | `personio:it-p` | `personio` | Employer-near ATS target; currently no observed loaded jobs. |
| `personio_otl_akademie_data_engineer_remote` | `personio:otl-akademie` | `personio` | Employer-near ATS target. |

Important terminology boundary:

```text
Connector family != source target != search profile != candidate source
```

The current system has four active connector/source families:

- Bundesagentur
- Greenhouse
- StepStone
- Personio

It has eight active source targets/search profiles.

Additional employer-origin candidates such as HDI, Rossmann, Finanz Informatik or WERTGARANTIE are not active ingestion targets yet. They should be treated as source candidates until selected, validated and added explicitly.

## Current Hot-Store and Silver Coverage

| Source target | Current raw jobs | Silver jobs | Interpretation |
|---|---:|---:|---|
| `greenhouse:stripe` | 602 | 12 | High raw volume, but substantial historical burden; raw count is not clean market volume. |
| `stepstone` | 172 | 9 | Useful commercial-market signal, but limited by defensive one-page acquisition. |
| `bundesagentur_fuer_arbeit` | 72 | 52 | Strong current Silver contribution, but also first-source time advantage. |
| `personio:eraneos` | 5 | 5 | Low volume, high employer-near value signal. |
| `personio:1komma5grad` | 2 | 2 | Low volume, employer-near signal. |
| `personio:otl-akademie` | 1 | 1 | Low volume, employer-near signal. |
| `personio:schluetersche-mediengruppe` | 1 | 1 | Low volume, employer-near signal. |
| `personio:it-p` | 0 | 0 | Active but no observed value so far; watchlist candidate. |

This table must not be interpreted as a simple source ranking. Each source has different acquisition semantics, history, filtering capability and risk profile.

## Current Run-Counter Baseline

| Source target | Runs | Loaded total from runs | Inserted total from runs | Duplicate total from runs | Current raw jobs | Raw jobs with valid run | Raw jobs without valid run |
|---|---:|---:|---:|---:|---:|---:|---:|
| `bundesagentur_fuer_arbeit` | 99 | 825 | 62 | 763 | 72 | 62 | 10 |
| `greenhouse:stripe` | 13 | 4510 | 602 | 3908 | 602 | 602 | 0 |
| `stepstone` | 49 | 1225 | 172 | 1053 | 172 | 172 | 0 |
| `personio:eraneos` | 13 | 29 | 5 | 24 | 5 | 5 | 0 |
| `personio:1komma5grad` | 13 | 15 | 2 | 13 | 2 | 2 | 0 |
| `personio:otl-akademie` | 10 | 7 | 1 | 6 | 1 | 1 | 0 |
| `personio:schluetersche-mediengruppe` | 9 | 2 | 1 | 1 | 1 | 1 | 0 |
| `personio:it-p` | 13 | 0 | 0 | 0 | 0 | 0 | 0 |

The run-counter baseline shows that the current hot store is generally consistent with run counters. The known exception is Bundesagentur.

## Counter Consistency Boundary

`ingestion_runs`, `raw_jobs`, `silver_jobs` and `source_value_snapshots` answer different questions.

| Data structure | Meaning |
|---|---|
| `ingestion_runs` | Historical process counters recorded when ingestion runs happened. |
| `raw_jobs` | Current Bronze hot-store rows after inserts, retention decisions and cleanup activity. |
| `silver_jobs` | Current canonicalized/relevant value evidence. |
| `source_value_snapshots` | Persisted evaluation points for source-value and windowed trend preview. |

These values must not be blindly equated.

Current finding:

- most source targets have `current_raw_jobs == inserted_total_from_runs`
- Bundesagentur has 10 current raw rows without `ingestion_run_id` and without `search_profile_id`
- those 10 rows were created on 2026-05-07 during the earliest BA ingestion/bootstrap phase
- they should be retained as early-ingestion evidence
- they should not be artificially backfilled into a run or profile because that would imply lineage certainty the project does not have

This is a lineage caveat, not a cleanup candidate.

## Source-Specific Interpretation Caveats

### Greenhouse

`greenhouse:stripe` currently contains substantial historical data burden.

The source was useful for learning and for exposing the difference between data volume and data value. However, the current raw volume must not be treated as clean market volume.

Known caveats:

- legacy broad/wildcard history exists
- many rows are classified as `archive_before_hot_store_removal_candidate`
- retained Silver-backed rows remain valuable evidence
- noisy historical rows should not be promoted into Gold/source-value trends
- future Greenhouse expansion must be source-targeted, locally filtered and small-batch

### Bundesagentur für Arbeit

Bundesagentur is currently the strongest Silver contributor.

Known caveats:

- it was the first implemented source and therefore has a time/tenure advantage
- it has a longer observation history than newer Personio targets
- it contains 10 early raw rows without run/profile lineage from the first bootstrap phase
- high Silver value is real, but comparisons with younger targets need coverage context

### StepStone

StepStone is intentionally constrained.

Known caveats:

- the connector fetches one complete search result page with 25 entries
- it does not perform a full fetch by design
- this is a defensive acquisition boundary based on operational and risk assessment
- lower volume compared with broad sources is partly a design decision, not only source weakness
- StepStone remains a useful market-discovery signal, not a preferred canonical employer-origin source

### Personio

Personio targets currently provide low-volume, employer-near signals.

Known caveats:

- the current batch is small
- `personio:it-p` has runs but no loaded jobs so far
- low volume does not automatically mean low value, because employer-near data may be more canonical than aggregator volume
- Personio expansion should continue in small batches with local multi-term filtering and source-value snapshots from day one

## Controlled Expansion Implication

The next expansion should be intentionally small:

```text
2–3 additional Greenhouse boards
1–2 additional Personio or ATS boards
optionally 1 highly relevant employer with a separate board if responsibly integrable
```

A candidate should only move into the first expansion batch when it has a clear rationale:

- employer-origin or ATS-near signal
- Germany, Hannover, remote or relevant market fit
- role relevance for Data Engineering, Analytics Engineering, Data Platform, Requirements, Product Owner or adjacent system/software roles
- stable and defensible access model
- local multi-term filtering can be applied when server-side search is not available
- source target can be measured separately in source-value snapshots
- expected value is not just raw volume

The first windows after adding new targets must be interpreted as coverage-affected windows, not as pure market movement.

## Next Step

The next S1 step should create a source-target selection matrix.

That matrix should classify candidate targets as one of:

- `candidate`
- `manual_review_needed`
- `parser_or_target_gap`
- `defer`
- `active`
- `watchlist`
- `do_not_build`

Known candidates such as HDI, Rossmann, Finanz Informatik and WERTGARANTIE should be carried into that matrix instead of being rediscovered ad hoc.
