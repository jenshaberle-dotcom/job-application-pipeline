# Deep Ocean Product V1 Control Center

This is the React presentation layer for the four operator-approved Pipeline product pillars.

## Architecture

```text
PostgreSQL Product V1 views
→ read-only Python API
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

Vite proxies `/api` and `/healthz` to the read-only Python server on port `8780`.

## Boundaries

- no provider call;
- no automatic application submission;
- no source or connector activation;
- no scheduler mutation;
- no POST-based product action API;
- no product decisions inside React;
- missing operator decisions and missing source documents remain visible blockers.
