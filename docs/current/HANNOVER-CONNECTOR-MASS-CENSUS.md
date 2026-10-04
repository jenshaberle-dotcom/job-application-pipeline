# Hannover Connector Factory Mass Census

Status: experimental, non-production. Tracking: #1166.

## Purpose

This experiment optimizes for **population size and structural variance**, not for a curated list
of currently attractive employers. Hundreds or thousands of technology-relevant companies are
valid inputs even when they currently expose no vacancy. Zero-job, no-career-surface and failed
connector cases are retained as evidence.

The intended flight is:

```text
public/company datasets
  -> mass seed corpus
  -> deterministic dedupe
  -> Employer-Origin discovery
  -> existing Classic connector lifecycle
  -> recipe/family reuse + qualification
  -> disposition/failure corpus
  -> later extraction/ML experiments
```

The mass census is deliberately a feeder, not a second connector authority. Classic's existing
Employer-Origin lifecycle remains authoritative. Cloud remains untouched.

## First seed geography

City of Hannover plus Region Hannover. "Tech" is deliberately broad: software, IT services,
telecom, cyber security, electronics, industrial automation, engineering, automotive, energy,
fintech/insurtech, logistics tech, digital agencies, e-commerce, medtech and adjacent technical
companies. False positives are preferable to premature filtering in this experiment.

The Region Hannover company database is a useful public seed source because it exposes industry,
activity focus and company size. Additional independent public directories should be combined;
source overlap is useful because duplicate rate is itself a measurement.

## Input

JSON, NDJSON/JSONL and CSV are accepted. Minimum field is company name. Useful optional fields:
`website`, `location`, `industry`, `source_record_id`.

Example:

```bash
python -m scripts.run_connector_mass_census \
  --seed /tmp/hannover-a.csv --source hannover-region \
  --seed /tmp/hannover-b.ndjson --source second-directory \
  --output /tmp/hannover-connector-census.json
```

## Metrics

The first stage records raw seeds, accepted/rejected seeds, unique companies, duplicates and
per-source contribution. Downstream stages must append origin-discovery coverage, career-surface
coverage, recipe/capability dispositions, qualification results, reused capability families,
generated artifacts, real-job counts and grouped failure fingerprints.

Do not collapse failures. The long tail is the experiment output.

## Safety/authority boundary

This slice performs no network requests, database writes, provider calls, source activation,
recurring scheduling or application action. A later live acquisition flight must be separately
admitted and should consume this immutable population by digest. Production connectors must not
be activated merely because the experiment generated or qualified a definition.
