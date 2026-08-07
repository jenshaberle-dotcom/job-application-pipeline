# Product V1 Controlled Activation Cap

Status: planned implementation slice

## Goal

Close the remaining Product V1 backend gap between exact S7U activation readiness and the first bounded employer-origin ingestion proof without enabling recurring ingestion.

Current accepted private-runtime evidence on 2026-08-07:

- `accompio`: `activation_readiness_supported`, 3/3 evaluable records, no active search profile.
- `computacenter`: `activation_readiness_supported`, 3/3 evaluable records, no active search profile.

## Architectural gap

`search_profiles.is_active = TRUE` currently makes a profile visible to the unfiltered daily `python -m src.ingest_jobs` run. Under PD-076 / Validated Connector Autonomy A1, controlled source activation is allowed after exact readiness, but recurring ingestion and scheduler mutation remain forbidden.

Therefore source activation and recurring-ingestion eligibility must be represented separately before Accompio or Computacenter is activated.

## Required behavior

1. Preserve `is_active` as source/profile activation truth.
2. Add an explicit recurring-ingestion eligibility flag with backwards-compatible defaults for existing profiles.
3. Unfiltered and source-family ingestion runs must select only recurring-enabled active profiles.
4. An exact explicit `--profile` run may execute an active controlled profile even when recurring ingestion is disabled.
5. Controlled activation must fail closed unless:
   - connector validation is passed / `ready_for_final_approval`;
   - final approval is passed / `approve_connector_registration`;
   - the A1 standing authorization is active;
   - a fresh S7U evaluation is exactly `activation_readiness_supported`;
   - no active profile already exists for the source.
6. Controlled activation creates exactly one bounded Hannover profile with page size 3 and recurring ingestion disabled.
7. Activation records a `connector_autonomy_authorization_events` entry for `controlled_source_activation`.
8. The first ingestion proof remains a separate explicit exact-profile command; no scheduler or provider action is introduced.
9. Silver processing is explicitly source-bounded.

## Boundary

- no provider/LLM calls
- no scheduler configuration mutation
- no recurring-ingestion enablement for controlled profiles
- no ranking mutation
- no application action
- no autonomous discovery-to-activation loop
- no activation unless fresh exact S7U readiness is supported

## Completion proof

For each supported target:

1. dry-run activation preflight reports exact A1 eligibility;
2. explicit apply creates one active, non-recurring profile;
3. unfiltered daily ingestion selection excludes that profile;
4. exact `--profile` first ingestion succeeds;
5. source-bounded Silver processing succeeds;
6. Product V1 / Golden Path is rerun against fresh DB state.
