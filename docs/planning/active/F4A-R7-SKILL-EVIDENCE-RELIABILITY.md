# F4A-R7 — Skill Evidence Reliability

Status: ACTIVE / deterministic hardening + read-only hybrid research

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

> External tools or ML may discover candidate evidence; only JAP-owned
> deterministic contracts may establish canonical Silver truth.

The JAP core therefore speaks only a small JSON span contract. Optional tools
run outside the core dependency graph. Their proposed values, taxonomy IDs,
confidence scores and classifications are diagnostic only. JAP validates exact
`start:end` spans against bounded employer-origin text and discards external
normalization when creating an `ObservedFact`.

Absence or failure of an optional observer must never make the normal JAP
pipeline unavailable.

## Preserved real-cohort evidence — 2026-09-15

Exact qualified head before this documentation commit:
`5f553e0e60ad3ad5e004987005ec95b38780290a`.

Qualification evidence:
- Pipeline CI `34953304355`: SUCCESS;
- Pipeline re-entry `34953304160`: SUCCESS;
- real read-only R7 cohort audit `34953300959`: SUCCESS;
- focused R7 contracts inside the audit: 32 passed + Ruff PASS;
- database migration state: 110/110 tracked, 0 pending, 0 checksum mismatch;
- no DB/Bronze/Silver/Product writes and no Candidate Fact / fit / ranking /
  Top-5 / application authority.

Real current cohort:
- 70 candidates;
- 67 reachable/audited;
- 3 origin-unavailable;
- 0 blocked origins;
- current deterministic Silver skills observed on 39/67 reachable jobs;
- 27 requirement-bearing jobs have zero current skills and are explicit
  `skill_recall_risk` rows.

Current source-family skill coverage:

| source family | current skill jobs | cohort jobs | observed ratio |
| --- | ---: | ---: | ---: |
| `finanz_informatik:hannover` | 0 | 11 | 0.000 |
| all current `www.f-i.de` rows | 3 | 16 | 0.188 |
| `hdi:hannover` | 4 | 9 | 0.444 |
| `generic_origin:valuny` | 1 | 2 | 0.500 |
| `generic_origin:hannover_ruck` | 15 | 21 | 0.714 |
| `personio:1komma5grad` | 7 | 9 | 0.778 |
| `personio:eraneos` | 7 | 7 | 1.000 |

### Requirement-section hardening result

A new provider-neutral requirement-section boundary was evaluated before any
Silver promotion. It recognizes bounded employer-visible requirement sections
and excludes navigation, cookie chrome, task sections and benefits where the
markup exposes useful semantic headings.

On the same real cohort it extracts a bounded requirement section for 40/67
reachable jobs. Current family results:
- Finanz Informatik: 16/16 current `www.f-i.de` rows;
- HDI: 9/9;
- 1KOMMA5: 9/9;
- Valuny: 2/2;
- Hannover Re: 3/21;
- Eraneos: 0/7, but current deterministic skill coverage is already 7/7;
- Clarios: 0/1, but the current deterministic skill row is already covered;
- enercity: 1/2.

This proves that the next deterministic gain is still primarily a semantic
section-boundary problem for selected markup families, not yet evidence that ML
is required everywhere.

### External Shadow result

The isolated `skill-extractor==0.2.0` gazetteer was run only as a Shadow candidate
finder. It is not in JAP runtime requirements and has zero Product authority.

Whole-page observation produced 3,905 incremental candidate spans across the
67 reachable jobs and contained unacceptable page-chrome noise.

After JAP-owned requirement-section narrowing, the same external observer
produced 610 incremental candidates across 40 jobs: roughly 84% less candidate
noise while retaining materially useful examples such as BPMN 2.0,
Datenmodellierung, Java, JavaScript, TypeScript, Spring Boot, IT-Sicherheit,
DORA, CISA, Excel, LLMs, Prompting, Fine-Tuning, REST, Git, CI/CD, Ansible,
Linux, ISTQB, MQTT and Modbus TCP.

The 610 candidates are still not promotable as a group. Remaining examples such
as `bis`, `drei`, `dem`, `ist` and other generic words prove that exact source
span alone is necessary but not sufficient for canonical skill truth.

## Deterministic-before-ML decision

R7 does not introduce a production ML dependency merely because ML could find
more spans. Deterministic extraction remains the primary lane while the
remaining misses are explainable by generic, reviewable rules.

Before deciding that a learned long-tail observer is needed, R7 should exhaust
these source-neutral deterministic levers:

1. bounded requirement-section recognition from visible headings and semantic
   JobPosting fields;
2. heading-language coverage for recurring German/English requirement phrases;
3. structured `skills`, `qualifications`, `experienceRequirements` and bounded
   `description` semantics where provenance is exact;
4. exact technical/certification tokens with strong morphology and boundary
   rules (for example language/tool names, standards, certifications and
   protocol/product identifiers);
5. phrase candidates whose meaning can be established without contextual
   inference;
6. deterministic rejection of page chrome, benefits and generic prose.

The deterministic lane is considered locally exhausted only when the remaining
false negatives require context to decide whether an exact span is a skill,
knowledge requirement or ordinary prose. Examples such as `Go`, `Spring`,
`Basic`, `Release`, `Control`, `science` or employer-specific concepts are the
intended long-tail boundary.

## Hybrid deterministic + ML long-tail direction

The planned long-tail architecture is parallel, not substitutive:

`bounded employer requirement text`
` -> deterministic extractor ---------------------> verified candidate spans`
` -> optional learned long-tail observer (Shadow) -> candidate spans`
` -> JAP exact-span + provenance verifier`
` -> deterministic policy / conflict handling`
` -> Silver only after qualification`

A learned observer therefore never decides Candidate Fact, fit, hard-filter,
ranking, Top-5 or application authority. It proposes spans and optionally a
confidence signal; deterministic JAP code owns acceptance and provenance.

## Current sample-size assessment for a JAP-owned ML model

The present 70-job cohort is useful as an evaluation and annotation seed, but it
is not a credible standalone training corpus for a new model from scratch.
Only 67 jobs are reachable and only 40 currently expose bounded requirement
sections through the first section extractor. Those 40 sections are also
clustered by a small number of employers, so a random job-level split would
leak source/template structure and overstate generalization.

The current sample is nevertheless promising for three immediate ML activities:

1. **zero-shot / pretrained model comparison** — no JAP labels required;
2. **weak-label and active-learning bootstrap** — deterministic positives,
   high-confidence external candidates and hard negatives can prioritize human
   annotation;
3. **small domain fine-tuning experiment** — only after an employer-held-out
   manually verified span set exists; hundreds of varied labelled requirement
   sections may be sufficient to test whether a pretrained NER/span model adds
   stable long-tail recall, but not to justify a model trained from scratch.

The ML experiment must use source/employer-held-out validation rather than a
random row split. Otherwise repeated employer templates can make a weak model
look artificially strong.

### ML promotion gate

No JAP-owned learned observer may move beyond Shadow until all are true:
- deterministic section recall has been hardened first;
- a manually verified exact-span gold set exists with positives and explicit
  hard negatives;
- train/validation/test partitions are held out by employer/source family;
- the learned observer adds recall specifically on deterministic misses;
- precision on its promoted subset is high enough that deterministic verification
  can fail closed rather than guessing;
- absence/failure of the model leaves the deterministic pipeline fully usable;
- model artifact, features, version and threshold are reproducible and pinned;
- the full Origin -> Bronze -> Silver -> Product -> Control Center path is
  requalified after any eventual Silver adoption.

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

1. Continue source-neutral deterministic requirement-section hardening, starting
   with recurring English variants currently missed by Hannover Re-style pages.
2. Re-run the exact same real cohort and quantify section recall and skill risk.
3. Evaluate the external context classifier only as a Shadow precision filter on
   already bounded requirement sections.
4. Build an annotation-ready exact-span sample with employer/source identity so
   future ML validation can be source-held-out rather than random-row-held-out.
5. Compare a lightweight JAP-owned pretrained/fine-tuned span model only after
   deterministic misses and a gold annotation set are explicit.
6. Promote only generic deterministic rules or, later, a tool-neutral learned
   observer whose incremental recall survives employer-held-out evaluation.
7. Re-run Origin -> Bronze -> Silver -> Product -> Control Center before the
   next operator acceptance.

## Acceptance direction

R7 is not accepted merely because a global skill count rises. It must show that
within-source-family variability is materially reduced and that known
requirement-bearing postings no longer routinely report `No explicit skills list
detected` when exact skill/knowledge/certification spans are visibly present.

Any eventual Silver promotion remains source-neutral, exact-span grounded and
fail-closed on ambiguity.
