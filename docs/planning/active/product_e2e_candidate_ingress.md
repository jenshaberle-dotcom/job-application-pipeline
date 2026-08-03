# Product E2E Generic Discovery Candidate Ingress

Status: implementation in review  
Risk: R2 bounded candidate-state creation behind exact operator approval  
Parent evidence: Product E2E Golden-Path audit run `20260803T111454458029Z`

## Evidence that triggered this slice

The first source-diverse E2E audit selected five real employers:

- an aggregator case stopped at `origin_url`;
- a Bundesagentur case stopped at `origin_candidate`;
- one existing-origin case stopped at `origin_inventory`;
- two existing-origin cases stopped at `connector_build`;
- no manual observation entered the five-case portfolio.

This does **not** justify pushing any named employer through a custom path. It shows
that the earliest reusable missing transition is discovery signal to reusable
employer-origin candidate, while later stages are already reachable for other
cases.

The absent manual class is not interpreted as proof that manual observations do
not exist. Manual observations share the general `market_evidence` source limit in
the current seed collector and can be displaced by newer automatic evidence. This
slice therefore collects manual observations through a separate bounded query
before source-diverse portfolio selection.

## Generic contract

The same candidate contract applies after any supported discovery ingress:

```text
StepStone/aggregator company signal
or Bundesagentur public-job signal
or Jens manual observation
→ normalized employer identity
→ duplicate check
→ explicit candidate-creation plan
→ exact operator-approved apply
→ employer-origin candidate in status discovery
→ origin URL still unresolved
```

The discovery source is provenance. It does not select a company-specific URL,
connector, gate threshold or downstream behavior.

## Source-specific evidence boundaries

### Aggregator company discovery

A bounded company observation may justify a discovery candidate. It is not origin
truth and does not prove that an employer career source exists.

### Bundesagentur public job API

A concrete public job signal may justify a discovery candidate when an explicit
employer identity is present. The BA URL remains discovery evidence and is not
written as the employer-origin URL.

### Manual observation

A manual observation may justify a discovery candidate only after a separate
`--include-manual-observations` opt-in. Manual provenance does not bypass identity,
origin, connector or Product V1 gates.

## Apply boundary

Dry-run is the default. Apply requires all of:

1. one or more exact `--company-key` values from the current plan;
2. `--apply`;
3. exact token `approve_product_e2e_discovery_candidate_creation`;
4. `--include-manual-observations` for any manual case.

The apply path:

- takes a transaction-scoped advisory lock per company key;
- rechecks company key and exact company name before insertion;
- creates only a row in `employer_origin_source_candidates`;
- sets `status = discovery`;
- leaves `candidate_url = NULL`;
- records discovery provenance in notes;
- commits no gate, connector, source, job, ranking or scheduler state.

## Execution

Plan only:

```bash
python -m scripts.run_product_e2e_candidate_ingress
```

Example explicit apply after reviewing the plan:

```bash
python -m scripts.run_product_e2e_candidate_ingress \
  --company-key example_company \
  --apply \
  --approval-token approve_product_e2e_discovery_candidate_creation
```

Manual observations additionally require:

```bash
--include-manual-observations
```

## Exit gate

This slice is complete when:

1. a source-diverse plan includes manual observations independently of general
   market-evidence recency pressure;
2. existing candidates are skipped deterministically;
3. a missing BA, aggregator or manual employer can be proposed through one shared
   contract;
4. apply is exact, deduplicated and explicitly approved;
5. candidate URL, gates, connector state and source activation remain untouched;
6. full CI and Ruff pass;
7. the operator runs plan mode against the live local database and reviews the
   actual candidate set before any apply.

After an approved candidate creation, the original Golden-Path audit is rerun. The
next implementation block is selected from the new earliest generic blocker, not
from a preferred employer.
