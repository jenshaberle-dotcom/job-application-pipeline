# DIAG-001 Generic Repair Diagnosis

Status: reference contract

DIAG-001 is a read-only diagnostic surface for repair and failure-pattern work.
It exists to prevent employer-specific debugging from becoming one-off pipeline
logic.

## Purpose

A concrete employer such as adesso, HDI or VHV may be used as a representative
case, but the diagnosis must answer a generic pipeline question:

> Which reusable capability is missing or weak, and would improving it help more
> than one candidate?

DIAG-001 therefore inspects schema, candidate identity, gate/evidence surfaces
and repair observability before any repair implementation is proposed.

## Boundary

DIAG-001 must not:

- write candidate state,
- write candidate URLs,
- write gate reviews or evidence,
- generate connector artifacts,
- register or activate sources,
- perform external HTTP/search requests,
- mutate Bronze, Silver, Gold or scheduler state.

## Required behavior

The diagnosis script must:

- run read-only against the local database,
- accept any `--company-key`,
- tolerate the project database config shape returned by `get_database_config()`,
- discover relevant public tables through `information_schema`,
- handle physical candidate identity columns such as `id` and domain-style
  identity columns such as `candidate_id`,
- use parameterized SQL and safe identifiers for dynamic table/column access,
- write JSON and Markdown reports under `exports/` when requested,
- keep the concrete employer as representative evidence only.

## Output contract

The JSON report contains:

- campaign name,
- read-only boundary,
- representative company key,
- schema contract,
- relevant table/column overview,
- representative candidate rows,
- rows mentioning the company,
- rows linked by candidate identity,
- generic diagnosis questions.

The Markdown report is intentionally compact and suitable for quick operator
review. It is not a Current Truth artifact.

## Relationship to REPAIR-001

REPAIR-001 ranks repair candidates. DIAG-001 explains why a ranked candidate is
stuck and which generic pipeline capability should be improved next.

DIAG-001 should normally be used before implementing a repair-agent change when
an individual employer exposes a suspected generic failure pattern.
