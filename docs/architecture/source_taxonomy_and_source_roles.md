# Source Taxonomy and Source Roles

## Purpose

The project intentionally separates **how data is acquired** from **why a source exists in the market-intelligence system**.

## Source Type

Source Type describes the technical acquisition mechanism.

Examples:

- Official API
- ATS API
- Career Site
- Aggregator
- Structured Job Board

Source Type answers:

> How is the data acquired?

---

## Source Role

Source Role describes the strategic role a source fulfills.

Examples:

- Company Discovery
- Market Discovery
- Origin Validation
- Ground Truth

Source Role answers:

> Why does this source exist in the system?

A source may fulfill multiple roles simultaneously.

---

## Examples

### StepStone

Type:

- Aggregator

Roles:

- Company Discovery
- Market Discovery

### Bundesagentur

Type:

- Structured Job Board

Roles:

- Market Discovery
- Ground Truth Baseline

### Greenhouse

Type:

- ATS API

Roles:

- Ground Truth

### HDI Career Portal

Type:

- Career Site

Roles:

- Ground Truth

---

## Source Value

Source value depends primarily on Source Role rather than technical Source Type.

### Discovery-oriented roles

Evaluate through:

- New Companies Discovered
- New Vocabulary Discovered
- Confirmed Origin Jobs
- Market Contribution

### Ground Truth roles

Evaluate through:

- Relevant Jobs
- Unique Jobs
- Data Quality
- Operational Stability

## Connector Generation Interpretation

Employer-origin connector generation is driven by Source Role, not only Source Type.

A career site, ATS-backed board or company platform becomes a connector-generation candidate when it can provide Ground Truth or Origin Validation value through bounded, defensively fetched job evidence.

S6A generation plans therefore evaluate whether a source candidate is useful as confirmed origin evidence before any connector artifact is generated.

## Aggregator Novelty and Saturation

Aggregator-role sources may be valuable even when they are not origin sources. Their value is evaluated through bounded market evidence, new-company discovery, vocabulary novelty and reassessment pressure.

Known-company or known-term repetition is not automatically bad, but repeated low-novelty cycles can indicate that a query is saturated and should be paused, refined through reviewed trial terms or redirected toward gate reassessment.
