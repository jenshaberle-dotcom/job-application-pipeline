# DEMO-001 operator UI hardening note

This bounded repo-only slice hardens the already-merged low-risk Control Center polish without changing Product V1, source, ranking, application, DB, provider, submission or send authority.

## Guarded operator behavior

- a click on any normal primary-navigation entry closes an active Data Layers portal first;
- `Escape` closes Data Layers as an explicit operator recovery path;
- the sticky top line says `Data Layers` while the portal is active rather than retaining the underlying hidden view label;
- decorative loading/navigation motion respects `prefers-reduced-motion`;
- the hardening guard performs no API request and no write.

The canonical acceptance boundary remains genuine local runtime/DB truth through `scripts/run_product_v1_live_demo.py --preflight-only` and the regenerated readiness artifacts. This note creates no local PASS evidence.
