# DEMO-001 application-readiness window hardening

This branch removes arbitrary `LIMIT 200` truncation from Product V1 job/application readiness reads, hardens direct script/module invocation, and adds operator-facing job filtering/sorting with newest-first default ordering. The local live proof reached `PRODUCT_V1_LIVE_DEMO=READY` after supplying the already-canonical private application document root. Remaining branch work is limited to wiring that same default root into the launcher before readiness probes so restart/re-entry does not depend on an operator-exported environment variable.
