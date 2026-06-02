# S7H — Origin Source Discovery Portfolio Probe

## Purpose

S7H extends the Origin Source Discovery Gate from a single-candidate check into a portfolio-level review. The goal is to see all current employer-origin candidates at once and decide which candidates can continue toward connector feasibility, which need manual origin-source review, and which must be stopped.

This is intentionally not a crawler. It evaluates persisted URL evidence only.

## Boundary

The portfolio probe keeps the same guardrails as the single-candidate gate:

- no web browsing
- no connector registration
- no source activation
- no Bronze writes
- no scheduler changes
- dry-run by default

## Commands

Run one candidate:

```bash
python -m scripts.run_origin_source_discovery_gate_agent   --company-key hdi   --reviewed-by jens
```

Run the current candidate portfolio as a dry-run:

```bash
python -m scripts.run_origin_source_discovery_gate_agent   --all-candidates   --reviewed-by jens
```

Persist the reviewed portfolio result:

```bash
python -m scripts.run_origin_source_discovery_gate_agent   --all-candidates   --reviewed-by jens   --write
```

Include already active controlled sources when you want a full portfolio health pass:

```bash
python -m scripts.run_origin_source_discovery_gate_agent   --all-candidates   --include-active   --reviewed-by jens
```

## Interpretation

- `selected` means a concrete public HTTPS career-like origin URL was selected from persisted evidence.
- `manual_review_required` means the system found evidence, but the origin source is ambiguous or not concrete enough.
- `blocked_unsafe_url` means the evidence is invalid, unsafe, non-HTTPS, local/private, or only aggregator evidence.

## Why this matters for the demo

The demo story is no longer "I built a crawler". The story is: market signals create candidates, the system gates origin-source evidence, only safe and meaningful sources continue toward connector feasibility, and every stop reason is visible.
