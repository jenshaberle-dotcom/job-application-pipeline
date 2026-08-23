# ML-PILOT-001B — Product V1 Operator Label Capture

Status: merged via PR #634 / merge `0241426929af5202a52da0436cad6e87981efeea`; runtime DB migration status proof pending

This slice operationalizes the already merged `operator_review_relevance` append-only label contract inside the canonical Product V1 Control Center.

The browser exposes exactly three explicit operator judgments for the selected Silver job: `interesting`, `not_relevant`, and `unsure`. It submits only the Silver job identity and the chosen label. All provenance is recomputed or assigned server-side from current repository/DB contracts.

A successful action may append only `job_review_relevance_label_events`. It cannot modify ranking, Top-5 membership, lifecycle state, source/connector state or application state, and it cannot start model/provider/GPU execution.

Repeated identical judgment on unchanged canonical Silver evidence is idempotent. Corrections append a new event that supersedes the prior event. Product V1 reloads persisted DB truth after each action instead of treating browser state as authority.

The repository implementation and CI are complete. Operational label capture still requires migration `101_create_job_review_relevance_label_events.sql` to be present in the configured local PostgreSQL runtime. A one-shot read-only self-hosted status proof checks that runtime state before any migration application is considered.

MLF-005 remains mandatory before collected labels may be materialized into a supervised dataset/split or used for model training.
