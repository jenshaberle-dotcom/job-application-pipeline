# SENSOR-001A Market Sensor Coverage Validation

## Purpose

SENSOR-001A validates market-sensor coverage before activating broader search
profiles. The immediate diagnostic case is Bundesagentur, but the rule is
generic: every market sensor must make two coverage intents explicit.

1. Local target-market search, currently Hannover / surrounding area.
2. Germany-wide remote-option search, expressed as the canonical intent
   `search_germany_wide_remote_options`.

This prevents a sensor from looking healthy only because it covers the local
Hannover market while silently missing remote-in-Germany opportunities.

## Boundary

This work item is validation-only. It does not activate a new BA profile, does
not mutate candidates or gates, does not perform external requests, and does not
write to the database. The runtime validation script opens a read-only database
transaction and exports JSON/Markdown evidence under `exports/`.

## Generic rule

A market sensor is incomplete when it has active local coverage but no active
profile expressing Germany-wide remote-option intent. The first concrete gap is
expected for `bundesagentur_fuer_arbeit`, because the archived SENSOR-001 note
already identified the BA setup as a local Hannover-region sensor rather than a
validated Germany-wide remote sensor.

The next safe action after detecting the gap is not broad activation. The next
safe action is a bounded validation profile design that compares local vs.
remote/nationwide yield, duplicate overlap, false-positive risk, and relevance
quality before activation.

## Expected follow-up

If SENSOR-001A confirms a remote/nationwide gap for BA, SENSOR-001B should design
a bounded validation profile. That follow-up should remain source-aware but not
source-specific: the same coverage expectation must later apply to StepStone,
ATS targets, employer-origin sensors, and any future API-oriented market sensor.
