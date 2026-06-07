# EO-002D Origin Source Discovery / URL Finder Repair

## Purpose

EO-002B/EO-002C showed a useful but uncomfortable result: controlled guest-list candidates can be selected and reported, but the URL Finder still returned `not_found` for the first benchmark pair.

Observed smoke result:

- `hannover_ruck`: tier D, `not_found`, no selected URL, false-negative candidate.
- `e_on_grid_solutions`: tier D, `not_found`, no selected URL.

EO-002D repairs the first concrete bottleneck without weakening downstream gates, changing the scheduler or adding new market sensors.

## Diagnosis

The Origin Source Discovery agent could already evaluate search-result context safely, but its deterministic fallback generation was too narrow for common corporate identity cases:

- `Hannover Rück SE` is often represented as `Hannover Re` / `hannover-re.com`.
- `E.ON Grid Solutions GmbH` belongs to the broader E.ON careers domain such as `eon.com` / `careers.eon.com`.

The pre-EO-002D candidate generator primarily spent its bounded probe budget on merged company-key/name variants. This could miss stronger corporate-alias domains before the `max_candidates` budget was exhausted.

## Implementation

EO-002D adds a bounded deterministic repair:

- corporate alias domain bases are generated before noisy company-key variants,
- alias-domain TLD probing is intentionally limited to `.com` and `.de`,
- high-value career paths are tried first for alias domains,
- job-host patterns such as `jobs.<domain>` and `careers.<domain>` are prioritized for alias bases,
- locality-only aliases such as `hannover` are not promoted into standalone domain bases,
- existing aggregator/domain safety guards remain unchanged.

## Boundaries

This block remains read-only from a pipeline perspective. It does not:

- write `candidate_url`,
- register connectors,
- activate sources,
- write Bronze/Silver/Gold records,
- change scheduler behavior (`no scheduler change`),
- weaken the Türsteher,
- bypass evidence gates.

## Expected Effect

The next EO-002B run should have better deterministic URL candidates before relying on external search providers.

Target benchmark expectations:

| Company key | Expected improvement |
|---|---|
| `hannover_ruck` | `jobs.hannover-re.com` or `hannover-re.com` candidates appear within the bounded default budget. |
| `e_on_grid_solutions` | `eon.com` / `careers.eon.com` candidates appear within the bounded default budget. |

A selected URL is still not guaranteed, because real HTTP probing and page content can legitimately fail. A continued `not_found` result after EO-002D is therefore decision evidence for deeper provider/search-result repair, not a reason to weaken gates.

## Validation

Targeted validation:

```bash
python -m pytest -q \
  tests/test_origin_source_discovery_agent.py \
  tests/test_origin_source_discovery_agent_selection_ranking.py \
  tests/test_eo002b_url_finder_validation.py \
  tests/test_eo002c_reprocessing_decision_report.py
```

Runtime smoke after merge:

```bash
python -m scripts.run_eo002b_url_finder_validation \
  --benchmark-label eo002d_url_finder_repair_smoke \
  --company-key hannover_ruck \
  --company-key e_on_grid_solutions \
  --target-location Hannover \
  --include-raw-results

python -m scripts.run_eo002c_reprocessing_decision_report \
  --benchmark-label eo002d_url_finder_repair_smoke \
  --report-json exports/eo002b_candidate_reprocessing_url_finder_validation/eo002d_url_finder_repair_smoke.json
```

## Next Decision

After the EO-002D smoke run:

- If A/B-tier selected URLs appear, proceed to gate-stop join and evidence-quality analysis.
- If only C-tier/manual-review candidates appear, improve review evidence and provider diagnostics.
- If D-tier `not_found` persists, improve external search-result acquisition/replay before changing gates or scheduler behavior.

## Runtime validation note

EO-002D should be validated with bounded HTTP probing during smoke tests.

Recommended smoke settings:

    --timeout-seconds 3
    --max-url-candidates 4
    --search-provider none

A previous unbounded/manual smoke run was interrupted during HTTP connection setup. This was not a URL-selection logic failure. It shows that default/full probing still needs a later runtime-hardening pass with total candidate-level budgets and clearer progress output.

Follow-up candidate: EO-002F URL Finder Runtime Hardening.
