# StepStone NOT Exclusion Stability Probe Result

## Purpose

This result documents EO-002A.2: validation of StepStone fetch-time exclusion using `NOT` syntax across active StepStone search terms.

Boundary: read-only, no detail pages, no pagination, no DB writes, no Bronze writes, no candidate creation, no connector activation.

## Summary

- Tested search terms: 7
- Tested non-baseline variants: 14
- Promising variants: 5
- Unreliable variants with known hits remaining: 7
- Weak or possible-drift variants: 2

## Result Table

| Search term | Variant | Known hits | Added companies | Relevance hits | Drift hits | Classification |
|---|---:|---:|---:|---:|---:|---|
| Data Engineer | baseline | 9 | 0 | 23 | 0 | baseline |
| Data Engineer | not_core | 0 | 13 | 23 | 1 | promising |
| Data Engineer | not_full | 0 | 14 | 21 | 1 | promising |
| Analytics Engineer | baseline | 7 | 0 | 18 | 1 | baseline |
| Analytics Engineer | not_core | 0 | 15 | 23 | 1 | promising |
| Analytics Engineer | not_full | 0 | 15 | 21 | 1 | promising |
| ETL | baseline | 3 | 0 | 20 | 0 | baseline |
| ETL | not_core | 3 | 5 | 20 | 0 | not_reliable_known_hits_remain |
| ETL | not_full | 0 | 0 | 0 | 0 | weak_refill_effect |
| Data Platform | baseline | 11 | 0 | 20 | 0 | baseline |
| Data Platform | not_core | 1 | 3 | 13 | 0 | not_reliable_known_hits_remain |
| Data Platform | not_full | 0 | 0 | 0 | 0 | weak_refill_effect |
| Data Warehouse | baseline | 8 | 0 | 16 | 4 | baseline |
| Data Warehouse | not_core | 0 | 10 | 9 | 9 | promising |
| Data Warehouse | not_full | 3 | 19 | 21 | 0 | not_reliable_known_hits_remain |
| Big Data | baseline | 8 | 0 | 17 | 1 | baseline |
| Big Data | not_core | 2 | 3 | 18 | 0 | not_reliable_known_hits_remain |
| Big Data | not_full | 6 | 17 | 20 | 0 | not_reliable_known_hits_remain |
| Python SQL | baseline | 6 | 0 | 19 | 0 | baseline |
| Python SQL | not_core | 7 | 4 | 19 | 0 | not_reliable_known_hits_remain |
| Python SQL | not_full | 6 | 16 | 21 | 0 | not_reliable_known_hits_remain |

## Interpretation

Minus syntax is rejected based on the previous feasibility audit.

`NOT` syntax remains viable as a fetch-time exclusion candidate, but only as a controlled probe mode. It must not be activated blindly in the daily scheduler before review.

## Next decision

- If several variants are promising: implement a controlled StepStone NOT-exclusion discovery probe.
- If results are unstable or drift-heavy: document rejection and move to bounded refill/search-term iteration.
- In both cases: no automatic candidate creation in this block.
