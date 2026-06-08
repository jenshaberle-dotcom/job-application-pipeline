# SENSOR-001 BA Remote / Nationwide Coverage Validation

Status: planned and promoted into the maturity roadmap; not implemented in EO-002E.

## Trigger

The live DB inspection showed that the Bundesagentur source currently has one active profile:

    ba_data_engineer_30629_50km

with location `30629`, radius `50 km` and active terms such as Data Engineer, Analytics Engineer, Big Data, Data Platform, Data Warehouse, ETL and Python SQL.

This means the current BA market sensor is a local Hannover-region sensor, not a validated Germany-wide remote sensor.

## Freeze Assessment

SENSOR-001 is not a White-Whale idea because it has a plausible 15 to 20 point impact on:

- Market Sensor Coverage
- False-Negative Control
- Recall
- Search Profile Quality

But it must remain a validation block first.

## Boundary

SENSOR-001 must not immediately activate a broad BA profile.

Required first step:

- preview/read-only validation
- small page size
- no scheduler change
- compare local vs remote/nationwide yield
- measure duplicate/noise/new-company rates
- decide later whether persistent profile activation is justified

## Position in Maturity Roadmap

SENSOR-001 is planned after EO-002E and before DOC-003 Adrian Reconciliation, so documentation can reflect both gate-stop reality and sensor-coverage reality.
