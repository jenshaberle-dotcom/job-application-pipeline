# S7K – Origin Source Discovery for Promoted Candidates

## Purpose

S7K tightens the Origin Source Discovery Gate after S7J promoted market-observed companies into explicit `discovery` candidates.

The key correction is semantic: a promoted candidate with only aggregator URLs is not an unsafe origin source. It is an origin-source evidence gap.

## Current Portfolio Behavior

For promoted candidates such as `dirk_rossmann`, `enercity`, `ratiodata`, `adesso` and `deutsche_bahn`, the gate may have market evidence from StepStone or similar exploration sources, but no confirmed employer-origin URL yet.

That state must be represented as:

- `discovery_status = not_found`
- `decision = manual_review_required`
- `blocker_code = market_evidence_without_origin_url`

It must not be represented as `blocked_unsafe_url`, because the candidate itself is not unsafe. Only aggregator URLs are unsuitable as origin sources.

## Safety Boundary

S7K keeps the S7D/S7H safety boundary unchanged:

- no web browsing
- no connector registration
- no source activation
- no Bronze writes
- no scheduler changes
- no CSV/Excel/export artifact as pipeline input

## Interpretation

This block separates three states that were easy to mix up:

1. no origin URL evidence exists yet,
2. only market/aggregator URL evidence exists,
3. unsafe URL evidence exists.

Only the third state should be blocked as unsafe. The first two states should remain visible as discovery work for the next Origin Source Discovery step.

## Next Step

The next implementation block should add a controlled origin-source evidence collection step for `discovery` candidates. That step may propose candidate origin domains, but must still require manual review when evidence is ambiguous or weak.
