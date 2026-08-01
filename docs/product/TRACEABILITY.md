# Product Traceability

Status: active product-governance rule

## Objective

The existing engineering backlog remains valuable, but it may no longer act as an implicit product specification.

Every active product-shaping story must demonstrate why it exists and which approved operator outcome it serves.

## Required links

Before implementation, a product-shaping story must reference:

- one or more approved `PRD-*` requirements;
- one or more approved `PD-*` decisions where applicable;
- one or more approved `PA-*` acceptance scenarios;
- the intended visible operator outcome;
- its side-effect and rollback boundary.

Example:

```json
{
  "story_id": "CC-012",
  "product_requirements": ["PRD-EVIDENCE-001"],
  "product_decisions": ["PD-050", "PD-055"],
  "acceptance_scenarios": ["PA-002-fewer-than-five-qualified"],
  "operator_outcome": "The review queue shows only jobs that satisfy the approved contract and explains omissions and uncertainty."
}
```

The example is structural only; open decisions are not implementation authorization.

## Backlog classification

Every engineering item should be classified as one of:

- `required_for_approved_product`;
- `enabling_technical_work`;
- `quality_security_or_reliability_control`;
- `product_change_proposal`;
- `optional_improvement`;
- `parked_future`;
- `not_required_for_current_product`.

Items without approved product traceability may remain in the catalog, but they may not enter the product critical path unless they are necessary safety, defect or operational controls.

## Authority boundary

The current codebase, database and merged PRs show what has been implemented. They do not automatically show what Jens wants.

When implementation and approved product intent disagree:

1. preserve data and operational safety;
2. record the mismatch;
3. classify the implementation as product drift or technical debt;
4. propose a bounded correction;
5. do not rewrite the approved product contract to match existing code.

## PR requirements

A product-shaping PR must state:

```text
Product requirements:
Product decisions:
Acceptance scenarios:
Visible operator outcome:
Product semantics changed: yes/no
Operator approval required: yes/no
```

A technical PR with no product semantic change should explicitly say so.

## Acceptance layers

1. **Technical correctness** — code, migrations and tests are correct.
2. **Contract conformance** — approved PRD requirements and scenarios pass.
3. **Operator acceptance** — Jens confirms that the visible behavior matches the intended product.

No lower layer substitutes for a higher one.

## Rebaseline sequence

1. confirm recorded repository truths;
2. resolve the highest-impact open decisions;
3. approve representative acceptance scenarios;
4. map the current critical-path backlog;
5. build a minimal vertical product slice;
6. run operator acceptance;
7. repeat for the next unresolved product surface.

This is a progressive product rebaseline, not a requirement to answer every future question before useful engineering resumes.
