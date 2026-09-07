# ML-LONGTAIL-001 — ML Long-Tail Job Detail Extraction Architecture

Status: parked / future architecture concept
Project: job-application-pipeline
Created: 2026-09-07
Activation: not part of the active roadmap or executable backlog
Runtime impact: none
Database impact: none
Scheduler impact: none
Current implementation impact: none

## Purpose

JAP should use a hybrid architecture for extracting job details from canonical or origin job pages.

Deterministic extraction remains the preferred path whenever the source exposes sufficiently reliable structure. Machine learning is reserved for the long tail: origin job portals whose HTML/DOM cannot be extracted completely and reliably through known structured interfaces or source/template recipes.

This document records the intended future architecture without creating implementation authority. It does not override `docs/planning/active/`, the Current Truth layer, the re-entry state, or existing source and Bronze/Silver boundaries.

## Architectural decision direction

The intended extraction order is:

```text
Origin Job URL
    |
    v
Deterministic extraction
    |-- ATS / job API
    |-- schema.org/JobPosting / JSON-LD
    |-- known source/template recipe
    |-- other unambiguous structured metadata
    |
    | insufficient / incomplete
    v
JAP ML Long-Tail Extractor
    |
    v
normalized raw extraction record
    |
    v
existing Bronze -> Silver normalization boundary
    |
    v
separate semantic job analysis
    |-- skills
    |-- languages
    |-- requirements
    |-- experience
    `-- other derived semantics
```

ML does not replace deterministic extraction. It is a source-independent fallback for pages where deterministic methods do not provide an adequate job-detail record.

A future implementation must define an explicit adequacy gate for deciding whether deterministic extraction is complete and trustworthy enough to avoid the ML fallback.

## Deterministic extraction remains first choice

The preferred extraction paths are, in principle:

1. ATS or job APIs intended for machine-readable access.
2. `schema.org/JobPosting`, JSON-LD, or equivalent structured job metadata.
3. Known source- or template-specific extraction recipes.
4. Other clearly structured metadata with deterministic semantics.

This preserves JAP's existing preference for official, employer-origin, ATS and canonical sources. Discovery sources may lead JAP to an origin job URL, but the job-detail extractor should prefer the most canonical and structured representation available.

## ML long-tail extractor

For unknown or insufficiently structured origin job portals, JAP may later introduce a source-independent model that extracts job fields directly from HTML/DOM.

The model should combine structural and semantic page information rather than treating the rendered page as plain text only. Candidate approaches include DOM-/markup-aware transformers such as MarkupLM and comparable DOM encoders or successor architectures.

This document does **not** select a final model family, checkpoint, serving stack or training framework.

### Target field mapping

The long-tail extractor should map DOM nodes or node spans to a canonical extraction schema such as:

- `TITLE`
- `COMPANY`
- `LOCATION`
- `WORKPLACE_TYPE`
- `EMPLOYMENT_TYPE`
- `SALARY`
- `DATE_POSTED`
- `DESCRIPTION`
- `APPLY_URL`

The exact persistence schema remains governed by the existing JAP Bronze/Silver architecture. The ML extractor should produce a normalized extraction envelope with provenance and evidence; it must not silently move downstream semantic interpretation into the extraction layer.

Where practical, a future record should retain enough evidence to answer which DOM node(s), attributes, structured fragment or page region supported an extracted value.

## Boundary to semantic job analysis

Job-detail extraction and semantic job analysis are separate concerns.

The long-tail extractor answers questions such as:

- What is the job title?
- Which company posted it?
- Where is it located?
- What employment/workplace type is stated?
- What salary/date/description/apply URL is present?

A separate downstream semantic layer may interpret the extracted description and related fields to derive:

- skills
- languages
- requirements
- experience level
- technologies
- responsibilities
- other semantic features

This separation prevents source extraction from becoming coupled to recommendation, ranking or candidate-profile semantics.

## Training-data strategy

Training data should be generated as automatically as possible from existing high-trust JAP information.

Primary supervision paths:

```text
ATS / API
    -> trusted ground truth
    -> DOM alignment
    -> training labels

JSON-LD JobPosting
    -> trusted ground truth
    -> DOM alignment
    -> training labels

Existing JAP deterministic connectors / recipes
    -> trusted ground truth
    -> DOM alignment
    -> training labels

Manual corrections
    -> reviewed gold labels
```

The key idea is to exploit pages where JAP already knows the answer from a high-confidence machine-readable or deterministic source, then align those values back to the HTML/DOM from the corresponding origin page.

A future dataset should preserve label provenance and trust level so API-derived, JSON-LD-derived, deterministic-recipe-derived and manually reviewed labels can be distinguished during training and evaluation.

### Public data candidates

The following external datasets or corpora should be investigated later for pretraining, benchmarking or additional supervision:

- SWDE
- Web Data Commons
- Common Crawl

Their usefulness, licensing/terms, field compatibility, markup freshness and source leakage risk must be evaluated before adoption. Their presence in this concept is an investigation target, not an implementation dependency.

## DOM alignment

The automatic-labeling pipeline should conceptually work as:

```text
trusted structured record
        +
corresponding origin HTML / DOM snapshot
        |
        v
value-to-node alignment
        |
        v
field-labeled DOM example
```

Alignment may later combine deterministic text normalization, attribute/link matching, DOM structure and semantic similarity. The implementation must preserve uncertainty instead of turning ambiguous alignments into unquestioned gold labels.

Manual corrections are the highest-value source for hard examples and should remain distinguishable from automatically aligned labels.

## Evaluation: source/template generalisation is the primary quality boundary

Randomly splitting different jobs from the same website is not sufficient evidence that the model solves JAP's long-tail problem.

Train, validation and test partitions must be separated by source and, where necessary, by template family. A hostname-only split is insufficient when the same ATS or page template appears across multiple domains.

The decisive benchmark is extraction performance on **completely unseen origin sources and/or templates**.

A future benchmark should therefore report at least:

- field-level extraction quality on unseen sources/templates
- critical-field coverage/completeness
- performance by field, not only one aggregate score
- performance by source/template family
- deterministic-only coverage versus deterministic + ML coverage
- fallback error rate, including cases where ML should have abstained

The benchmark should explicitly prevent leakage from near-identical templates between training and test data.

## Confidence, abstention and evidence

The ML path should not be forced to return a value for every field.

A future production design should support:

- per-field confidence or equivalent calibrated evidence
- missing/unknown outputs
- abstention when the page is outside the learned distribution
- provenance back to the origin HTML/DOM
- comparison against deterministic extraction when both paths produce a value

Conflicts between high-confidence deterministic data and ML predictions should not be silently resolved in favor of ML.

## Long-term learning loop

Deterministic extractors and the ML model can eventually reinforce each other:

```text
new deterministic source coverage
    -> new trusted DOM-aligned labels
    -> stronger long-tail model
    -> better unknown-source coverage
    -> newly observed recurring templates
    -> candidate deterministic recipes / additional reviewed labels
    -> stronger deterministic + ML coverage
```

This creates a compounding data advantage as JAP encounters more origin sources.

The feedback loop must retain provenance. ML predictions must not automatically become gold labels merely because the model produced them; independent deterministic evidence, review or another explicit trust rule is required to avoid self-training drift.

## Relationship to existing JAP architecture

This future concept is intended to extend, not replace, existing architecture decisions:

- connector-based acquisition remains the source abstraction
- canonical/employer/ATS sources remain preferred over aggregators where feasible
- Bronze remains source-preserving
- Silver remains the canonical normalization boundary
- semantic analysis remains downstream from source extraction

The ML extractor is therefore a future capability inside the origin-detail extraction path, not a new ingestion architecture and not a replacement for JAP connectors.

## Deferred implementation scope

No implementation work is authorized by this document.

Explicitly deferred:

- model selection or MarkupLM adoption
- HTML/DOM snapshot dataset design
- DOM alignment implementation
- training pipeline and experiment tracking
- serving/runtime architecture
- confidence calibration and abstention thresholds
- public-dataset ingestion
- benchmark harness
- production fallback activation
- automated deterministic-recipe discovery from ML evidence

These are future work items only after the concept is intentionally re-entered into active planning.

## Suggested re-entry criteria

Revisit this concept when several of the following are true:

1. Deterministic origin-detail extraction is stable enough to provide trustworthy supervision.
2. JAP has a measurable coverage gap caused by unknown origin sources/templates rather than by missing deterministic engineering work.
3. Sufficient source-diverse HTML/DOM + ground-truth examples can be produced without contaminating the unseen-source benchmark.
4. The project can retain reproducible DOM snapshots and label provenance for training/evaluation.
5. A source/template-held-out benchmark can be run before any production fallback is enabled.
6. The expected coverage gain justifies the additional ML training, serving and observability complexity.

Until then this file remains a parked architecture concept under `docs/planning/future/` and must not displace the active E2E/product path.