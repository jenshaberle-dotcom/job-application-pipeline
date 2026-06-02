# S7P Reviewed Origin URL Repair Application

## Purpose

S7P closes the lowest-risk part of the Search Intelligence feedback loop:
when S7N detects that a selected origin URL is stale or not reachable but also
finds a concrete repair candidate, and S7O surfaces that as
`origin_url_repair_required`, S7P can apply the reviewed repair to
`employer_origin_source_candidates.candidate_url`.

This is intentionally narrower than connector build approval. It only repairs
URL evidence so the feasibility probe can be rerun against the corrected origin
source.

## Boundary

S7P does not:

- build connector artifacts,
- register connectors,
- activate sources,
- write Bronze records,
- change scheduler configuration,
- promote candidates or bypass approval gates.

## Expected current use case

The first expected queue item is adesso:

- previous URL: `https://www.adesso.de/de/karriere/jobs/index.jsp`
- repair candidate: `https://www.adesso.de/de/karriere/jobs/index.html`

The repair URL still has to pass the existing origin-source URL safety policy:
public HTTPS URL, career-like path, no known aggregator, no private/local host.

## Commands

Dry run:

```bash
python -m scripts.run_origin_url_repair_application_agent   --company-key adesso   --reviewed-by jens
```

Persist reviewed repair:

```bash
python -m scripts.run_origin_url_repair_application_agent   --company-key adesso   --reviewed-by jens   --write
```

Then rerun feasibility for the repaired candidate:

```bash
python -m scripts.run_connector_feasibility_probe_agent   --company-key adesso   --reviewed-by jens

python -m scripts.run_connector_feasibility_probe_agent   --company-key adesso   --reviewed-by jens   --write
```

## Self-Repair Loop Guard

S7P can successfully apply a reviewed repair candidate while S7N still reports the repaired URL as unreachable. In that case, S7O must not recommend the same repair again.

If `url_repair_candidate_url` already equals the current candidate URL, the queue treats the item as renewed origin-source discovery or manual URL review work instead of `origin_url_repair_required`. This keeps the repair flow audit-friendly and prevents repeated no-op repairs.

