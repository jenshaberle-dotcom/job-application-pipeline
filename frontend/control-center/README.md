# Deep Ocean Product V1 Control Center

This is the React presentation layer for the four operator-approved Pipeline product pillars.

## Architecture

```text
PostgreSQL Product V1 views and reviewed evidence tables
→ read-mostly Python API with narrow action allowlist
→ React / TypeScript Control Center
```

The existing Jinja2 Control Center remains available as an operational fallback during migration. Product and gate decisions stay in database/read-model or Python domain contracts, not in React components.

## Local build

```bash
cd frontend/control-center
npm install
npm run build
cd ../..
python -m scripts.run_product_v1_control_center
```

Development mode:

```bash
python -m scripts.run_product_v1_control_center
cd frontend/control-center
npm run dev
```

Vite proxies `/api` and `/healthz` to the Python server on port `8780`.

## Reviewed POST actions

The server exposes only narrowly allowlisted operator actions whose scope is owned by Python/DB contracts:

- `/api/v1/source-connectors/final-approval` records the existing reviewed final-approval gate;
- `/api/v1/product-v1/job-review-label` appends explicit `interesting`, `not_relevant` or `unsure` operator evidence for the scoped ML review-relevance target.

The job-review client may submit only the exact Silver job ID and one frozen label. Reviewer identity, timestamps, evidence cutoff, Silver-evidence fingerprint, sampling reason and signal-exposure provenance are server-owned. Repeated identical feedback on unchanged evidence is idempotent; a changed judgment appends a superseding event rather than editing history.

## Boundaries

- no provider call;
- no model training, Kaggle execution or GPU activation;
- no automatic application submission;
- no source or connector activation;
- no scheduler mutation;
- no arbitrary POST/database mutation API;
- operator review labels do not change ranking, Top-5 membership, lifecycle or application state;
- no product decisions inside React;
- missing operator decisions and missing source documents remain visible blockers.
