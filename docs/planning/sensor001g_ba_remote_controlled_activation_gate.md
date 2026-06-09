# SENSOR-001G BA Remote/Nationwide Controlled Activation Gate

SENSOR-001G turns the SENSOR-001F recommendation into a controlled activation gate for the BA remote/nationwide review profile.

## Purpose

SENSOR-001E produced a bounded external BA sample, and SENSOR-001F converted the result into a decision recommendation. SENSOR-001G does not run another sample and does not ingest jobs. It checks whether the recommendation is actionable and exposes the exact activation target before any database mutation.

## Boundaries

Default mode is dry-run only.

Dry-run guarantees:

- no external requests
- no database writes
- no raw_jobs or ingestion_runs writes
- no scheduler mutation
- no candidate/gate/connector mutation
- no Bronze/Silver/Gold mutation

Apply mode is intentionally gated:

- `--apply` is required
- the exact confirmation token is required
- only the BA remote/nationwide review profile may be updated
- the update only flips `search_profiles.is_active` from false to true
- no ingestion run is executed by SENSOR-001G

## Operator flow

First run the dry-run gate:

    python scripts/run_sensor001g_ba_remote_controlled_activation_gate.py

Review the JSON/Markdown export. Only after explicit approval, run:

    python scripts/run_sensor001g_ba_remote_controlled_activation_gate.py \
      --apply \
      --confirm ACTIVATE_BA_REMOTE_NATIONWIDE_REVIEW_PROFILE

## Why this is separate from SENSOR-001F

SENSOR-001F is a read-only decision layer. SENSOR-001G is the explicit apply gate. Keeping them separate preserves the project rule that product/pipeline mutation must not be hidden inside analysis or recommendation reports.

## Follow-up

After controlled activation, the next useful review is not broad activation. The next review should inspect the first scheduled/controlled BA remote run result and compare whether the sample signal transfers into actual pipeline value.
