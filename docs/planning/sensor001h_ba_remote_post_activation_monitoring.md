# SENSOR-001H BA Remote/Nationwide Post-Activation Monitoring

## Purpose

SENSOR-001H observes the controlled BA remote/nationwide review profile after
SENSOR-001G activation without triggering ingestion and without changing pipeline
state.

The work item exists because SENSOR-001F found enough bounded sample signal to
recommend controlled activation, and SENSOR-001G made the profile active under an
explicit approval gate. SENSOR-001H keeps the next step bounded: measure the next
visible effect before broadening activation or changing discovery/gate logic.

## Scope

SENSOR-001H may:

- read the current BA remote/nationwide profile state;
- read active terms for the profile;
- read ingestion_runs/raw_jobs counters for that profile;
- export a JSON/Markdown monitoring report;
- classify the state as awaiting first run, observed, failed, or attention needed.

SENSOR-001H must not:

- call external sources;
- create ingestion runs;
- write raw_jobs;
- activate or deactivate profiles;
- mutate scheduler state;
- mutate candidate, gate, connector, Bronze, Silver, or Gold state;
- turn monitoring output into an activation-retention decision by itself.

## Expected first state

Immediately after SENSOR-001G activation, the expected safe state is usually:

```text
monitoring_ready_awaiting_first_run
```

This means the profile is active and ready to be observed, but no normal
post-activation ingestion run has been measured yet.

## Decision boundary

SENSOR-001H is not a source-quality decision. It is a monitoring readiness and
first-observation report. A later work item should interpret observed runs, for
example:

- `SENSOR-001I BA Remote First Run Review`;
- `MARKET-002A Sensor Promotion Quality Review`;
- `STEPSTONE-002A Discovery Cycle Quality Review`.

## Validation

```bash
python -m pytest -q tests/test_sensor001h_ba_remote_post_activation_monitoring.py
python scripts/run_sensor001h_ba_remote_post_activation_monitoring.py
python scripts/run_validate001_unified_validation.py --profile commit
git diff --check
```
