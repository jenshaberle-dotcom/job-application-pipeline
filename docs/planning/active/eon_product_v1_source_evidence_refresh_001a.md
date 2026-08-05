# E.ON Product V1 Source Evidence Refresh 001A

Status: implementation for issue `#359`  
Boundary: exact persisted E.ON pilot assessment only

## Product gap

The exact E.ON job is already a controlled Product V1 reference case. Its
employer-origin description is stored in the authorized Bronze record, while the
persisted partial assessment intentionally left languages, work model and
requirements seniority unknown.

The source now supports a narrower conclusion:

- fluent German and English are explicitly required;
- hybrid work is explicitly offered;
- several years of professional experience are explicitly required.

The assessment row cannot be silently overwritten. Its previous state must remain
recoverable and auditable.

## Controlled refresh

The refresh runner is bound to:

- raw job `26342`;
- Silver job `466`;
- source `successfactors:eon_germany`;
- external ID `eon_germany:1414903533`;
- title `(Senior) Data Engineer Data & AI (f/m/d)`;
- the authorized E.ON pilot provenance contract.

Plan-only is the default. Apply requires the exact token:

`EON-PRODUCT-V1-SOURCE-EVIDENCE-REFRESH-001`

The Apply transaction:

1. obtains an advisory transaction lock;
2. revalidates the exact Raw/Silver binding and stored assessment;
3. rebuilds the evidence from the stored description;
4. inserts one immutable assessment revision containing the exact before/after
   payloads and source-evidence excerpts;
5. updates only the bounded assessment columns;
6. validates the assessment, hard-filter evaluation and Product V1 readiness;
7. commits both the revision and assessment update together.

A replay verifies the existing revision and target assessment and performs no
second update or insert.

## Deterministic evidence rules

### Languages

German and English must occur close together and the same local evidence window
must contain an explicit fluency marker such as fluent, business-fluent,
verhandlungssicher or fließend.

Mentioning both languages without a fluency requirement is rejected.

### Work model

Hybrid must be explicitly connected to work, working, model, setup or arrangement.
A phrase such as `hybrid cloud` is not accepted as work-model evidence.

### Requirements seniority

The exact `(Senior)` title marker must still be present and the description must
explicitly require several, multiple or many years of professional experience, or
a German equivalent.

## Updated fields

Only these assessment fields may change:

- `required_languages` → `["de", "en"]`;
- `language_evidence_status` → `observed`;
- `work_model` → `hybrid`;
- `requirements_seniority` → `senior`;
- `seniority_evidence_status` → `observed`;
- source-grounded explanations;
- removal of the three resolved uncertainties;
- assessor metadata.

## Preserved unknowns and gates

The refresh must preserve:

- `weekly_hours_min = NULL`;
- `weekly_hours_max = NULL`;
- `weekly_hours_evidence_status = unknown`;
- `capability_fit_status = unknown`;
- all ranking scores as `NULL`;
- direct and derived hard-filter status as `unknown`;
- Product V1 readiness as `hard_filter_evidence_required`.

After the refresh, the expected hard-filter components are:

- employment: `passed`;
- languages: `passed`;
- weekly hours: `manual_review_required`;
- seniority and capability fit: `manual_review_required`;
- overall hard filter: `unknown`.

The remaining required evidence is therefore exactly:

- numeric weekly hours;
- authoritative candidate capability fit.

## Explicit non-goals

This slice does not:

- fetch or refresh the vacancy over the network;
- call a provider or LLM;
- activate a source, connector or scheduler;
- create Bronze, Silver or location rows;
- infer 35–40 hours from `Part or Full time`;
- decide candidate capability fit;
- generate ranking scores or force a Top-5 result;
- generate or submit an application.

## Runtime proof

Issue closure requires private PostgreSQL evidence for:

1. migration 087 applied without checksum drift;
2. plan-only extraction of `de`, `en`, hybrid and senior requirements;
3. controlled Apply with one revision insert and one assessment update;
4. readiness remaining `hard_filter_evidence_required`;
5. replay with zero new revision/update operations;
6. report validation and explicit remaining evidence of weekly hours and
   capability fit only.
