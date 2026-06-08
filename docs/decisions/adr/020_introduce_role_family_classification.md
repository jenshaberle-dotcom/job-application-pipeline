# ADR 020: Introduce Role Family Classification

## Status

Proposed

## Context

The project currently normalizes relevant jobs into the Silver layer and prepares dashboard-oriented Gold views.

However, source-level and title-level aggregation is not sufficient to understand the actual job market landscape.

Different sources may use different titles for similar roles, and many job titles combine multiple domains.

Examples:

- Product Owner Data Platform
- Requirements Engineer Software
- BI Consultant
- Data Platform Engineer
- Agile Requirements Manager
- Machine Learning Engineer

To support matching, dashboard analytics and personal job market intelligence, the project needs an explicit role family classification layer.

## Decision

The project will introduce role family classification as a separate semantic enrichment feature.

The first implementation should be rule-based, transparent and testable.

It should not be implemented as a simple dashboard-only aggregation.

Initial classification should produce at least:

- primary role family
- classification method
- confidence score
- matched rule trace

Later versions may add:

- secondary role family
- description-based classification
- skill-based classification
- embedding-based or LLM-assisted classification
- manual feedback loops

## Initial Role Families

The initial taxonomy should be small and aligned with the project goals.

Candidate role families:

- `data_engineering`
- `data_analytics_bi`
- `data_science_ml`
- `product_ownership`
- `requirements_engineering`
- `agile_coaching`
- `software_engineering`
- `systems_engineering`
- `devops_platform_engineering`
- `other_unknown`

## Consequences

### Positive

- enables dashboard analytics by role family
- improves job market intelligence
- supports future matching logic
- makes classification decisions explainable
- keeps semantic enrichment separate from dashboard aggregation
- allows quality control and test coverage

### Negative

- adds classification complexity
- requires rule maintenance
- may introduce false positives and false negatives
- requires taxonomy discipline
- needs explicit handling of ambiguous roles

## Future Implementation Notes

A future implementation may introduce a dedicated table:

- `job_role_classifications`

Potential fields:

- `silver_job_id`
- `primary_role_family`
- `secondary_role_family`
- `classification_method`
- `confidence_score`
- `matched_terms`
- `created_at`

The implementation should include tests for representative job title examples and known ambiguous cases.

## Related Documentation

- `docs/reference/scoring-and-gates/role_family_classification.md`
- `docs/archive/visualization/dashboard_vision.md`
- `docs/planning/active/roadmap.md`
