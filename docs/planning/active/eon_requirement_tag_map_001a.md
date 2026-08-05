# E.ON Requirement Tag Map 001A

Status: implementation for Issue `#374`

## Product reason

The exact E.ON requirement inventory is runtime-proven for raw job `26342` / Silver job `466`. It preserves eight employer statements with stable `eon-req-*` identities, but a later Candidate Fact comparison still needs explicit semantic grouping.

This slice creates only the employer-side canonical tag map. It does not compare candidate evidence and does not create a fit result.

## Exact source contract

The mapper accepts only inventory key `EON-REQUIREMENT-INVENTORY-001` with the eight runtime-proven statements in their exact order, text, statement keys and normalized text hashes.

It fails closed when:

- the inventory key differs;
- statement count differs from eight;
- any statement is missing or reordered;
- any statement key, exact text or normalized hash changes;
- a statement has no tags;
- a tag is duplicated or violates the canonical tag syntax.

## Canonical tag groups

The exact employer statements map to these semantic groups:

1. professional data-engineering experience and consulting background;
2. end-to-end data-solution delivery;
3. software-development best practices, version control, CI/CD, monitoring, automation and testing;
4. Kubernetes, Airflow, Kafka, containerization and Helm;
5. Microsoft Azure, infrastructure as code and secure cloud architecture;
6. Azure Data Factory, Databricks, Terraform, Python and Spark;
7. stakeholder communication and audience adaptation;
8. fluent English and fluent German.

The resulting map contains 26 unique canonical tags. It preserves statement text and source hashes alongside the tags.

## Obligation truth

Every mapping records:

- `source_expectation_class = profile_statement`;
- `obligation_strength = unspecified`.

The employer wording does not explicitly use `must`, `required`, `preferred`, `nice to have` or an equivalent priority marker. This slice therefore does not infer:

- hard-filter status;
- mandatory versus preferred priority;
- weighting;
- substitutability;
- seniority-based importance;
- tool-bundle completeness requirements.

## Stable identity

`tag_map_sha256` binds:

- tag-map key;
- source inventory key;
- original description SHA-256;
- profile section SHA-256;
- statement order and keys;
- normalized statement hashes;
- expectation and obligation fields;
- canonical tags.

Any source or mapping drift changes the map hash or fails closed.

## Runtime command

```bash
.venv/bin/python -m scripts.run_eon_requirement_tag_mapping \
  --raw-job-id 26342 \
  --silver-job-id 466
```

The runner uses the exact existing E.ON binding and a PostgreSQL read-only transaction. Its report is local and marked `review_output_only_not_pipeline_input`.

## Preserved boundaries

- zero database writes;
- zero Candidate Fact reads or writes;
- no capability-fit decision or score;
- no assessment, readiness, ranking or Top-5 mutation;
- no weekly-hours inference;
- no provider, LLM or network request;
- no source, connector or scheduler activation;
- no application action.

## Completion condition

Issue `#374` remains open until the exact private read-only runtime produces eight mappings, 26 unique tags, stable source/map hashes and zero side effects.

A later separate slice may compare this reviewed employer tag map with an approved real private Candidate Fact profile. That comparison is not authorized here.
