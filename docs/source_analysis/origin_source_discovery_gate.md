# S7D – Origin Source Discovery Gate Foundation

## Purpose

Origin Source Discovery is now an explicit gate before connector feasibility and connector artifact generation. The system must not silently assume that a discovered company name already implies a safe, concrete and correct origin source URL.

The gate answers one narrow question:

> Which persisted URL evidence is safe and concrete enough to be treated as the candidate's origin source for later connector analysis?

## Boundary

This foundation is intentionally conservative:

- no web browsing or probing inside the gate
- no connector registration
- no source activation
- no Bronze writes
- no scheduler changes
- no CSV/Excel/export artifact as pipeline input

The gate evaluates already persisted evidence from tables such as `employer_origin_source_candidates` and `aggregator_novelty_items`.

## Worst-case risks avoided

The worst outcomes would be:

1. treating an aggregator or unrelated page as an employer-origin source,
2. probing unsafe or local URLs,
3. generating a connector for the wrong company/domain,
4. silently turning a homepage guess into a connector target,
5. making a later approval look safer than it really is.

For that reason, the gate requires public HTTPS evidence and prefers career-like URL paths such as careers, jobs, karriere or stellen. Homepage-only evidence is routed to manual review instead of being promoted automatically.

## Decisions

Possible gate states:

- `selected` – a public HTTPS career-like URL was selected.
- `manual_review_required` – plausible evidence exists, but it is not concrete or unambiguous enough.
- `blocked_unsafe_url` – only invalid, non-HTTPS, local/private or otherwise unsafe URL evidence exists.
- `not_found` – no URL evidence is available.
- `not_applicable` – reserved for candidates where origin source discovery is irrelevant.

## CLI

Dry run:

```bash
python -m scripts.run_origin_source_discovery_gate_agent --company-key hdi --reviewed-by jens
```

Persist the gate result:

```bash
python -m scripts.run_origin_source_discovery_gate_agent --company-key hdi --reviewed-by jens --write
```

## Demo interpretation

This is the missing bridge between market/candidate discovery and connector-generation planning. The system no longer behaves as if the origin source URL appeared by magic. It records the selected URL, confidence, rejected alternatives, blocker reason and boundary conditions in PostgreSQL.
