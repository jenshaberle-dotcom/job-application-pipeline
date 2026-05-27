# ADR-030: Define Trend Eligibility and Source Coverage Boundary

## Status

Accepted

## Context

The project now persists `source_value_snapshots` and has a read-only window preview for 24h, 7d and 30d source-value windows.

This makes source trends technically visible, but technical window output is not automatically a reliable market signal.

Two distortion risks must be handled before Gold views or dashboards interpret trends:

1. **Metric semantics**: some metrics indicate source activity or pipeline throughput, but not market value.
2. **Source coverage changes**: adding or removing sources, source targets, search terms or filtering semantics can change observed volume without any real market movement.

The project also completed Historical Burden Analysis before implementing windowed trends. That analysis showed that raw volume can contain legacy broad-match data, commercial aggregator history or test/transient records. Therefore, trend logic must distinguish current operational evidence from historical burden and coverage effects.

## Decision

The project will treat windowed source-value output as trend evidence only when both conditions are met:

1. the window has sufficient trend maturity, and
2. the interpreted metric is trend-eligible for the question being asked.

Additionally, any source-target, search-term or filtering change inside an interpreted window must be treated as a **coverage change**, not as pure market movement.

G1 therefore separates:

- window mechanics
- trend maturity
- metric trend eligibility
- source coverage effects
- future Gold/dashboard interpretation

Source-coverage expansion remains encouraged, but it must be controlled and annotated. The project should not delay source expansion until after dashboards are built, because late expansion would make early market trends artificially narrow. At the same time, the project must not repeat broad undifferentiated full-fetch ingestion that creates historical burden without proportional value.

## Trend-Eligible Metric Boundary

The current `source_value_snapshots` metrics should be interpreted as follows:

| Metric or metric family | Default interpretation | Gold readiness |
|---|---|---|
| `silver_jobs_delta` | Stronger indicator of new canonical value when transformation coverage is stable. | Trend-eligible with maturity and coverage context. |
| `raw_jobs_delta` | New unique Bronze rows in the hot store; can be inflated by source coverage changes or source-specific uniqueness semantics. | Support signal, not standalone market trend. |
| `matched_jobs_after_filter_delta` | Source activity, repeated matches or throughput after filtering. | Activity signal, not standalone value signal. |
| `duplicate_rate_delta_pct` | Duplicate pressure and source overlap/pipeline behavior. | Source-quality signal, not market growth signal. |
| `failure_rate_delta_pct` | Operational health and source reliability. | Trend-eligible for health, not job-market value. |
| `latest_lifecycle_state` / `latest_recommendation` | Current source lifecycle summary. | Decision support only after mature windows and coverage context. |
| all-time raw totals | Historical baseline. | Not Gold trend signal without retention and burden interpretation. |

Future Gold views must not collapse these into one generic "source value trend" without preserving interpretation context.

## Source Coverage Change Boundary

A source-value window is coverage-affected when any of the following changes happens inside or near the interpreted window:

- a new source is introduced
- a new source target is introduced, for example another Greenhouse board or Personio feed
- a source target is removed, paused or deprecated
- local post-fetch filtering changes materially
- active search terms change materially
- source-target lineage or source-family semantics change
- historical burden is removed from, or excluded from, the operational hot store

Coverage-affected windows may still be useful, but they must be interpreted as:

```text
observed pipeline/source coverage changed
```

not automatically as:

```text
the job market increased or decreased
```

This is especially important before controlled Greenhouse, Personio or other ATS expansion. Adding several new employer boards can increase raw, matched or Silver counts even if the underlying market is unchanged.

## Controlled Source Coverage Expansion

The project should expand source coverage before serious Gold/dashboard interpretation, but expansion must be targeted.

Preferred expansion pattern:

1. choose a small batch of relevant source targets
2. document why each target is relevant
3. preserve source family, source target and source type semantics
4. use local multi-term filtering where server-side search is unavailable
5. generate source-value snapshots from day one
6. treat the first windows after expansion as coverage-affected
7. evaluate uniqueness, Silver contribution, duplicate pressure and operational risk before further expansion

The project should avoid:

- broad Greenhouse wildcard or full-fetch batches without target rationale
- large undifferentiated company-board lists
- treating source volume as value without Silver or origin evidence
- comparing pre-expansion and post-expansion windows as pure market trends

## Consequences

### Positive

- prevents dashboards from confusing source expansion with market growth
- keeps the Greenhouse Stripe lesson visible in architecture
- allows controlled source expansion without blocking all analytics work
- makes Gold-readiness depend on metric semantics, not only SQL availability
- supports a cleaner professional project story

### Negative

- adds another interpretation layer before Gold dashboards
- requires source-target changes to be tracked and explained
- early windows after expansion may be less useful for market trend claims
- some attractive metrics remain activity indicators rather than value indicators

## Implementation Notes

G1 now consists of:

1. read-only source-value window preview
2. trend-maturity indicators
3. trend-eligible metric boundaries
4. source-coverage change boundaries

The next implementation phase should be controlled source coverage expansion, not broad dashboard interpretation.

After controlled expansion, the project can return to Gold-readiness and search-term contribution analysis with a better source base.

## Related ADRs

- ADR-024: Define search quality and relevance evaluation boundary
- ADR-025: Preserve search-term lineage for quality evaluation
- ADR-026: Define source acquisition scope, canonical source strategy and source value evaluation
- ADR-027: Define source target acquisition model
- ADR-028: Separate source family, source target and source type
- ADR-029: Define historical burden retention strategy
