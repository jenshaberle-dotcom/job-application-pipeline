# ADR-025: Preserve search-term lineage for quality evaluation

## Status

Accepted

## Context

The project executes one ingestion run per active search term inside a search profile.

Search-quality evaluation needs to answer questions such as:

- which search terms create useful observations
- which search terms mostly produce duplicates
- which search terms produce noisy matches
- which search terms uniquely discover valuable jobs
- how search terms behave differently across sources

The existing schema links `ingestion_runs` to `search_profiles`, but it does not preserve the specific `search_terms` row or term text used for a run.

This makes later search-term quality analysis unreliable because multiple terms can belong to the same profile.

## Decision

Persist search-term lineage on `ingestion_runs`.

Each ingestion run may store:

- `search_term_id`: foreign key to `search_terms` when available
- `search_term`: text snapshot of the executed search term

The text snapshot is intentionally stored in addition to the foreign key so historical runs remain understandable even if search-term configuration changes later.

`job_observations` do not need a separate search-term column at this stage because observations can inherit term context through their `ingestion_run_id`.

## Consequences

### Positive

- enables reliable search-term quality metrics
- supports duplicate and overlap analysis by term
- preserves historical evidence for profile calibration
- keeps observation rows compact
- avoids parsing requested URLs to infer terms

### Negative

- adds small schema and repository changes
- older ingestion runs may not have term lineage unless backfilled manually
- future term renames require careful interpretation of historical metrics

## Follow-up

After this lineage exists, the project can add Bronze/Gold-style views for:

- observations per search term
- unique jobs per search term
- duplicate observation rate per search term
- search-term overlap within a profile
- jobs discovered by exactly one term
