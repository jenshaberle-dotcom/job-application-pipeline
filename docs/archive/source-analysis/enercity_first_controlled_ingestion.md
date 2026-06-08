# S7W enercity First Controlled Ingestion Run

## Summary

S7W executed the first controlled ingestion run for the previously activated `enercity:discovery` source target.

## Boundary

- Source activation already happened in S7V via migration `051_activate_enercity_discovery_source_target.sql`.
- This run executed exactly the bounded active profile `enercity_discovery_hannover_precision`.
- No scheduler changes were made.
- No additional source targets were activated.
- No CSV/Excel/export artifacts were used as pipeline inputs.

## Bronze Result

- profile: `enercity_discovery_hannover_precision`
- source: `enercity:discovery`
- requested URL: `https://www.enercity.de/karriere/jobsuche`
- ingestion run id: `527`
- status: `success`
- total loaded: `1`
- inserted count: `1`
- duplicate count: `0`
- raw job id: `11872`
- title: `Cloud Infrastructure & DevOps Engineer (f/m/d) – Azure Focus`
- company: `enercity AG`

## Silver Result

- controlled Silver command: `python -m src.run_silver_jobs --source enercity:discovery --limit 10`
- silver job id: `196`
- raw job id: `11872`
- decision: `included`
- reason: `relevant_for_silver`
- canonical source type: `employer_origin_career_site`
- canonical key candidate: `enercity ag :: cloud infrastructure & devops engineer (f/m/d) – azure focus :: hannover; remote; deutschland; hybrid | de`

## Validation

- `python -m compileall src scripts tests`
- `pytest -q`
- result: `460 passed`

## Notes

S7W added enercity support to the Silver transformer and added a controlled `--source` / `--limit` interface to the Silver runner so new source targets can be transformed deliberately instead of broad-running unrelated sources.
