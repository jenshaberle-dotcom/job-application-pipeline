# Origin Learning Pipeline

Status: active architecture contract

## Goal

Employer-origin understanding happens before normal Bronze/Silver product processing. Market sensors discover companies and provide vocabulary hints, but they are not normal Product job sources.

## Canonical chain

```text
Market sensor / company discovery
  -> employer-origin candidate
  -> origin proof (reachable, bounded, source-valid)
  -> company vocabulary learning on the proved origin
  -> vocabulary-guided job discovery on the origin
  -> structure learning on one or more real origin job pages
  -> normalized Origin Bronze evidence
  -> parser-family selection
  -> Silver normalization
  -> lifecycle / assessment / ranking / Control Center
```

## Stage contracts

### 1. Company discovery

Market sensors may discover companies, titles and terminology. Their job rows are discovery evidence only and must not become normal Product review jobs.

### 2. Origin proof

A candidate career site or ATS becomes eligible for deeper learning only after the existing bounded proof/gate path marks it source-valid. Proof is not activation and does not create Silver jobs.

### 3. Vocabulary learning

Vocabulary learning is company-scoped and origin-scoped after proof. It may reuse market vocabulary as a prior, but the proved employer origin is the preferred authority for company-specific title and role language.

Learned terms are evidence, not search-profile mutation. They may drive the next bounded origin job-discovery pass only through an explicit execution projection.

### 4. Job discovery from learned vocabulary

Use the learned company vocabulary to find one or more real vacancy URLs on the proved origin. The discovery result remains source-local and keeps exact origin URL / identifier evidence.

### 5. Structure learning

Observe the selected real vacancy pages before Bronze normalization. Learn, at minimum:

- ATS / portal family
- job-detail URL patterns
- structured `JobPosting` availability
- title / company / description fields
- source-published and valid-through fields
- one-to-many locations
- remote / workplace signals
- source-local requisition or structured identifier
- stable vacancy identity evidence

Structure learning does not create ranking or application authority.

### 6. Origin Bronze

Bronze persists normalized evidence from the real origin page while retaining source-local identity and provenance. It must carry enough evidence for downstream freshness, location and semantic-dedup decisions.

### 7. Parser family -> Silver

Silver must not depend on one bespoke parser per employer when multiple origins share a stable portal structure.

Parser selection priority:

1. proven parser family / ATS cluster,
2. source-specific parser only when no shared family is safe,
3. generic structured `JobPosting` parser,
4. generic bounded DOM/text fallback with lower evidence confidence.

The parser's output target is the canonical Silver field set. It normalizes source fields; it does not overwrite provenance.

## Product review scope invariants

- `All jobs` is current Product review truth, not a Bronze/Silver archive.
- market-sensor rows do not enter normal Product review scope.
- only lifecycle-current origin jobs are normal current opportunities.
- `Published` means source-published date when observed.
- `First JAP observed` means the earliest persisted JAP observation of that vacancy.
- multi-location vacancies remain one vacancy when source-local identity proves they are one posting.
- exact origin URL / requisition identity wins over title+location heuristics for deduplication.

## Near-term implementation order

1. Move company vocabulary learning behind proved origin candidates while keeping market vocabulary as a prior.
2. Feed learned vocabulary into bounded origin vacancy discovery.
3. Promote structure observation into the pre-Bronze chain and persist parser-family / identity / location metadata.
4. Make Silver parser-family aware.
5. Harden Control Center review scope: current origin-only, First JAP observed, multi-location projection, semantic dedup.
6. Continue normal Product assessment / capability fit / hard filter / ranking.
