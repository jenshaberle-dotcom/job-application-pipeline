# S7N-QUERY-PARAMETER-JOB-DETAIL-RECOGNITION-001

Status: implementation validation  
Issue: #398  
Parent runtime chain: #392  
Completed replacement authority: #395 / PR #397

## Runtime evidence

After the approved Accompio and Computacenter URL replacements, exact no-write
S7N probes produced a clean split:

- Computacenter exposed 18 concrete path-based job-detail candidates and reached
  `likely_feasible`;
- Accompio exposed dynamic job-list structure but zero detail candidates and
  remained `structural_evidence_without_job_detail`.

The current public Accompio board exposes concrete jobs through URLs shaped like:

```text
https://karriere.accompio.com/de?id=458ccb
```

The historical classifier uses path segments to identify concrete detail pages.
A stable query identifier on the same shallow locale path is therefore invisible
to the path-only detail rule.

## Generic completion

The active S7N runner gains a bounded completion layer that promotes a link only
when all conditions hold:

- public HTTPS;
- not an aggregator, social host, asset or technical endpoint;
- same registered domain as the reviewed origin;
- origin or destination host is explicitly job/career-oriented;
- destination remains on the same board path, a generic job path or a shallow
  locale path;
- exactly one bounded job identifier query is present;
- any additional parameters are bounded company, tenant or locale scope;
- the anchor label is role-like.

Recognized identifier keys are normalized forms of:

```text
id
jobId
vacancyId
postingId
requisitionId
reqId
positionId
openingId
```

## False-positive controls

The completion rejects:

- tracking-only query strings;
- redirect-like query parameters;
- unrelated or lookalike hosts;
- non-job hosts;
- empty or oversized identifiers;
- generic labels such as `Mehr`, `Details`, `Bewerben` or `Apply` without role
  evidence.

When the same URL was previously classified as career context or noise, the
query-detail projection replaces that contradictory classification instead of
counting both.

## Decision preservation

Query structure alone is insufficient. At least one trusted concrete query-detail
URL must exist before S7N can produce:

```text
likely_feasible
continue_to_connector_build_planning
```

The completion grants no persistence or downstream build authority.

## Boundary

This slice authorizes no:

- provider or LLM request;
- database migration or runtime write;
- feasibility-review persistence;
- connector artifact generation, registration or activation;
- Bronze, Silver or Gold mutation;
- scheduler or Wave change;
- ranking, Top-5, Candidate Fact or application mutation.

## Runtime acceptance

After CI and merge:

1. rerun Accompio and Computacenter through the unchanged S7N no-write CLI;
2. verify `persisted_review_id: -`;
3. verify review/item counts remain unchanged;
4. classify exact review-persistence gates from the refreshed evidence;
5. rerun the unchanged Product E2E connector-build bridge only after any
   separately approved review persistence.
