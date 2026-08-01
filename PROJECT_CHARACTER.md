# Project Character

Status: active product-governance contract
Class: **A — Intent Locked**
Product owner and operator: **Jens**

## Governing principle

```text
Exact on WHAT.
Adaptive on HOW.
```

The Job Application Pipeline is a personal product whose behavior must match the operator's target model. DON and other engineering agents may choose, challenge and improve technical solutions, but they may not independently redefine the product.

## Operator-owned product semantics

The following are product decisions and require explicit operator approval before they become repository truth:

- target user and usage rhythm;
- target role families and profile hierarchy;
- Hannover, commuting, hybrid and remote rules;
- hard inclusion and exclusion criteria;
- job freshness and source-evidence requirements;
- Top-5 meaning and quality threshold;
- ranking factors and treatment of uncertainty;
- distinction between concrete jobs, employer observations and research candidates;
- review journey and permitted operator actions;
- automatic actions and prohibited automation;
- Product V1 scope and success metrics.

DON may propose changes to these surfaces only as `product_change_proposal`. A proposal does not become active truth until the operator accepts it.

## Engineering freedom

Within the approved product contract, DON may independently propose and implement:

- database models, views and migrations;
- services, agents and module boundaries;
- algorithms that conform to approved product semantics;
- vertical implementation slices;
- tests, diagnostics and observability;
- performance improvements and refactoring;
- evidence-based changes to technical sequencing.

Engineering freedom does not include changing product meaning to make implementation easier.

## Authority order

When artifacts disagree, use this order:

1. operator-approved product contract and decision records under `docs/product/`;
2. approved product acceptance scenarios;
3. current product and architecture truth under `docs/current/`;
4. active roadmap and backlog catalog;
5. code, tests, migrations and runtime evidence for implementation truth;
6. reference and archive material for context only.

Code can prove what exists. It cannot silently redefine what the product should do.

## Delivery gates

Product-shaping work requires:

1. an approved product requirement;
2. at least one representative acceptance scenario;
3. traceability from backlog item to requirement and scenario;
4. automated conformance where feasible;
5. final operator acceptance for the visible product behavior.

Safety fixes, defect repairs, read-only evidence gathering and operational stabilization may proceed without waiting for every open PRD decision, provided they do not introduce new product semantics.
