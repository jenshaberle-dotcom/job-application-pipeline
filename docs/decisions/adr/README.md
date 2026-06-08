# Architecture Decision Records (ADRs)

Status: current ADR navigation
Scope: ADR directory after DOC-001K rebaseline
Last rebaseline: DOC-001K

This directory contains Architecture Decision Records (ADRs) for the project.

ADRs preserve architectural reasoning over time. They are not automatically
Current Truth just because their repository status says `Accepted`.

Use the DOC-001K status table before treating an ADR as an implementation anchor:

- `docs/decisions/adr_status_table.md`

## DOC-001K reader rule

When an ADR conflicts with the Current Truth layer, resolve in this order:

1. active safety and governance contracts,
2. `docs/current/architecture.md`,
3. `docs/current/system-diagrams.md`,
4. `docs/decisions/adr_status_table.md`,
5. the individual ADR file.

## Status vocabulary

| DOC-001K status | Meaning |
|---|---|
| Current | Still an active architecture decision. |
| Superseded | Replaced or materially narrowed by a newer decision. |
| Historical | Useful context but not an active architecture rule. |
| Needs rewrite | Important decision area, but the ADR text/status must be reconciled before use. |

## ADR index

The complete row-level classification lives in
`docs/decisions/adr_status_table.md`.

Current highlights:

- ADR-017 is superseded for the active UI path by ADR-032 Jinja2 Control Center Template Layer.
- ADR-019 needs rewrite before dedicated heartbeat/source-health implementation.
- ADR-020 needs rewrite before role-family classification becomes an active pipeline feature.
- ADR-031, ADR-032 and ADR-033 are current anchors for visual identity, Control Center template boundaries and Search Intelligence safety/security.

## Maintenance rule

When adding, renaming or retiring an ADR, update
`docs/decisions/adr_status_table.md` and run:

```bash
python scripts/check_adr_rebaseline.py --json
```

The ADR table is intentionally separate from this README so navigation stays
small while the control surface remains complete and testable.
