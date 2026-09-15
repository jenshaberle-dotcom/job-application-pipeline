# F4A-R7 — Skill Evidence Reliability

Status: ACTIVE / research + read-only qualification first

## Operator finding

The R6 operator surface is materially clearer, but skill evidence is not yet
reliable enough for Product acceptance. Skill extraction varies both across and
within otherwise working source families. Valuny can expose useful ML skills,
while Finanz Informatik is largely blind and Hannover Re / 1KOMMA5 show mixed
coverage.

R7 therefore re-enters at the Origin/Bronze semantic boundary. UI work is not the
primary task until skill recall is measurably more stable.

## Existing limitation

The current generic path prefers structured `JobPosting.skills`. When that field
is absent, the deterministic fallback is intentionally bounded but relies on a
small fixed skill vocabulary. This is high precision but structurally low recall
for employer-specific domain knowledge, certifications, methods and newly
emerging technologies.

## External research

R7 may adopt external ideas and optional observers when they improve measurable
reliability. External components never become required JAP runtime dependencies
or authority sources.

### 1. SkillSpan / job-market skill extraction research

- SkillSpan (NAACL 2022) treats skill extraction as span extraction from job
  postings and demonstrates the benefit of domain-adapted models.
- 2024 surveys and LLM studies reinforce that skill extraction and skill
  classification/linking are separate tasks.
- Entity Linking in the Job Market Domain (2024) links already identified skill
  spans to ESCO rather than using taxonomy linking to invent the source span.
- SkiLLens (EACL Industry 2026) likewise separates candidate-skill retrieval
  from ESCO linking in a multilingual pipeline.

Implication for JAP: first prove an exact employer-origin span; taxonomy mapping
is downstream metadata and cannot establish the existence of the skill.

References:
- https://aclanthology.org/2022.naacl-main.366/
- https://arxiv.org/abs/2401.17979
- https://aclanthology.org/2024.nlp4hr-1.1/
- https://aclanthology.org/2024.nlp4hr-1.3/
- https://aclanthology.org/2026.eacl-industry.65/

### 2. dreamjobs-tech/skill-extractor

Repository: https://github.com/dreamjobs-tech/skill-extractor

Useful properties:
- MIT licensed;
- job-posting-specific 30k+ skill gazetteer;
- exact candidate spans;
- optional MiniLM + MLP context classifier trained on job postings;
- relatively small quantized model option.

Limitation: the context classifier is English-trained. R7 therefore uses only
its gazetteer as an optional Shadow candidate finder initially. Its canonical
skill names and classifier decisions have no JAP authority.

### 3. GLiNER

Repository: https://github.com/urchade/GLiNER

Useful properties:
- zero-shot span NER with exact offsets and scores;
- multilingual Apache-2.0 model available;
- suitable as an independent recall comparator.

Limitation: the multilingual model is materially heavier than JAP needs for the
first R7 iteration. It remains an optional research comparator, not a runtime
requirement.

### 4. ESCO / multilingual job-market models

- ESCO is available from the European Commission in 28 languages and supports
  local/downloaded use.
- ESCOXLM-R shows that job-domain + taxonomy-aware multilingual pretraining can
  materially improve span-level job-market tasks.
- Nesta and Tabiya implementations independently use the same broad split:
  extract entities/spans first, then map/link them to a taxonomy.

References:
- https://esco.ec.europa.eu/en/use-esco/download
- https://aclanthology.org/2023.acl-long.662/
- https://github.com/nestauk/ojd_daps_skills
- https://github.com/tabiya-tech/tabiya-livelihoods-classifier

## Architecture rule

> External tools may discover candidate evidence; only JAP-owned contracts may
> establish canonical Silver truth.

The JAP core therefore speaks only a small JSON span contract. Optional tools
run outside the core dependency graph. Their proposed values, taxonomy IDs,
confidence scores and classifications are diagnostic only. JAP validates exact
`start:end` spans against the bounded employer-origin text and discards external
normalization when creating an `ObservedFact`.

Absence or failure of an optional observer must never make the normal JAP
pipeline unavailable.

## R7 read-only audit

`scripts/run_f4a_r7_skill_reliability_audit.py` measures, for every current
review job and per source family:

- structured JobPosting availability;
- requirement-section signal availability;
- current Silver skill status and skill count;
- rows with requirement evidence but zero extracted skills (`skill_recall_risk`);
- optional external exact-span candidates;
- incremental spans not currently represented by Silver skills.

No database writes, Candidate Fact reads, fit/ranking authority or raw HTML
persistence are allowed.

## First optional observer

`scripts/external_observers/dreamjobs_skill_extractor_observer.py` is research
only. It is intentionally not included in JAP requirements. In an isolated
research environment it may use `skill-extractor==0.2.0` to propose gazetteer
spans. The tool-neutral JAP validator decides whether a proposed span is exact;
no external normalized value is promoted.

## Adoption sequence

1. Run the normal deterministic R7 audit across the current cohort.
2. Run the same cohort with the optional gazetteer observer in isolation.
3. Compare source-family recall risk and incremental exact spans, especially
   Finanz Informatik, Hannover Re, 1KOMMA5 and Valuny.
4. Use GLiNER / existing LLM booster only as independent Shadow comparators for
   remaining misses, not as Product authority.
5. Promote only generic verifier rules or a tool-neutral lexicon/span capability
   that demonstrates materially higher recall without unacceptable false
   positives.
6. Re-run Origin -> Bronze -> Silver -> Product -> Control Center before the
   next operator acceptance.

## Acceptance direction

R7 is not accepted merely because a global skill count rises. It must show that
within-source-family variability is materially reduced and that known
requirement-bearing postings no longer routinely report `No explicit skills list
detected` when exact skill/knowledge/certification spans are visibly present.

Any eventual Silver promotion remains source-neutral, exact-span grounded and
fail-closed on ambiguity.
