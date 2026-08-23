# REENTRY-001A Job Application Pipeline Re-Entry Decision

Status: current repository re-entry; deterministic acquisition hardening exhausted for the bound 40-candidate cohort
Date: 2026-08-24
Repository: `jenshaberle-dotcom/job-application-pipeline`
Repository ID: `1230805345`
Current deterministic Pipeline baseline: `880db5f0ae02d2450265f639d245d7bdcec59014`
Boundary: repository and Runtime evidence are project truth; chat is not project truth

## Purpose

REENTRY-001A is the repository-backed continuation point for the Job Application
Pipeline. The June 2026 MCP re-entry decision is retained as repository history,
but its former GENERIC/EXPAND next action is stale and no longer controls work.

The deterministic acquisition hardening campaign has now been driven to its
current evidence-supported stopping point. The bound 40-candidate cohort improved
from `21/40` proven and `19/40` blocked to `23/40` proven and `17/40` blocked
without increasing the request budget, weakening genuine-job proof, adding
company-specific exceptions, or introducing provider/LLM/Tavily side effects.

## Required reads

Before continuing from this point, authenticate the repository ID above and read:

1. this file completely;
2. Pipeline issue `#522` (`LLM-BOOST-001`) as the LLM/search booster authority and
   downstream handoff for sparse, novel, or semantically difficult residuals;
3. `docs/planning/active/ml_learning_foundation_lane.md` and
   `docs/reference/search-intelligence/booster_admission.md` as the parallel ML
   learning-lane and task-specific ML-vs-LLM admission authorities; neither is
   superseded by `#522` or by this deterministic exhaustion decision;
4. merged deterministic PRs `#615`, `#616`, `#623`, and `#639`;
5. Runtime repository `jenshaberle-dotcom/job-pipeline-runtime`, issue `#203`;
6. Runtime V4 40-cohort run `32670547466`, result commit
   `32f8cf904de6165c7aa60c2b74de00d41f263473`;
7. Runtime V16 run `32671012052`, result commit
   `c4b540658de4f083230361ef96dd8da7928e283a`, matrix
   `carriers/connector-residual-evidence-v16/32671012052/matrix.json`;
8. Runtime PR `#255`, merged as
   `bf8a8b8305b9e25a7f9d20bb2073a23472778ab3`, which removed the stale fixed
   19-residual assumption from the V16 diagnostic workflow without changing
   acquisition behavior.

Do not substitute assistant memory, chat summaries, retired NEXT artifacts, or
stale generated summaries for these sources.

## Deterministic hardening delta

Relevant generic hardening already merged includes:

- `#615`: repaired the Deloitte deterministic acquisition path;
- `#616`: added bounded sibling fallback after a discovered detail attempt fails;
- `#623`: extended the existing shared fourth-request grant only to strict
  same-host `stellenmarkt` / `stellenanzeige` detail paths carrying a terminal
  numeric requisition identity;
- `#639`: removed an implementation drift by reusing that same strong requisition
  boundary in the form-aware V4 acquisition lane. No new navigation family was
  introduced.

Pipeline PR `#639` merged at
`880db5f0ae02d2450265f639d245d7bdcec59014` after focused positive/negative
regression coverage and the full repository validation suite passed.

## Current measured 40-cohort baseline

The post-`#639` Runtime V4 proof is authoritative for the current deterministic
baseline:

- Pipeline snapshot: `880db5f0ae02d2450265f639d245d7bdcec59014`;
- Runtime run: `32670547466`;
- result commit: `32f8cf904de6165c7aa60c2b74de00d41f263473`;
- input: `40`;
- genuine-job acquisition proven: `23`;
- blocked: `17`;
- blocked cause: `no_genuine_job_detail` for all 17;
- logical network requests: `110`;
- connectors using the shared extra request: `12`;
- connectors using a metered form request: `9`;
- proof-job persistence: `0`.

Compared with the prior post-`#623` control baseline (`21/40`, `19/40` blocked),
`#639` adds two genuine-job proofs. Both are Materna records that previously
stopped after root -> `/suche` -> `/stellenmarkt`. The form-aware lane now spends
the already-authorized shared fourth request on the strict requisition detail
`.../stellenmarkt/...-j2110.html`, which returns `jsonld_jobposting` proof.

## Deterministic contract

The deterministic layer remains governed by these hard boundaries:

- base request budget remains `3` logical requests;
- exactly one existing bounded extra request may be shared across authorized
  deterministic transitions;
- absolute logical request cap remains `4`;
- genuine-job acceptance/content proof is unchanged;
- no provider, LLM, or Tavily request is part of deterministic acquisition;
- no DB, Product, source activation, scheduler, or application mutation;
- no raw HTML, form values, or raw API-response persistence;
- no company-specific special case merely to raise the cohort score;
- ambiguous evidence fails closed.

A deterministic extension is allowed only when fresh evidence exposes a generic,
bounded rule that satisfies the same contract.

## Fresh residual V16 evidence

Runtime V16 run `32671012052` is bound to the post-`#639` 17-case residual and
completed all diagnostic lanes V7-V15 successfully with zero diagnostic
execution failures.

Lane result-entry counts:

- V7: `17`;
- V8: `14`;
- V9: `15`;
- V10: `11`;
- V11: `1`;
- V12: `17`;
- V13: `15`;
- V14: `0`;
- V15: `0`.

The diagnostic boundary remained clean: acceptance unchanged; DB/Product/source
activation absent; provider/LLM/Tavily requests `0`; raw HTML/API persistence
absent.

The evidence does not support another generic deterministic acquisition rule:

- V8 exposes provider/listing controls and known ATS-family hints, but no newly
  authorized genuine-job detail transition;
- V9 is replay-only (`new_navigation_attempted=false`) and records API/form
  indicators rather than a proven new route;
- V11 finds one JOIN public-widget bundle for TrustYou, but no candidate IDs or
  candidate URLs;
- V12 performs bounded standard same-host sitemap probes; observed inventories
  produce no accepted detail-shape URL for the residual cases;
- V13 probes explicit static assets. It reports one API-ish route candidate in
  total, for Compugroup Medical: `/api/kd-gdpr-cc`, a GDPR/cookie endpoint rather
  than a job API. Workday CXS route evidence remains absent for the relevant
  Workday cases;
- V14 selects zero explicit GET job-API routes;
- V15 selects zero explicit job-link routes.

Provider detection by itself is not authority to invent a provider route.
Likewise, a generic JSON-POST transport capability is not evidence for a route.
No Workday/company-specific path is authorized from this matrix.

## Deterministic exhaustion decision

For the current bound 40-candidate cohort and the current acquisition contract,
deterministic acquisition hardening is **exhausted at `23/40` proven and `17/40`
blocked**.

This is an evidence-backed stop condition, not a claim that the remaining jobs
are impossible to acquire. It means no additional generic deterministic rule is
supported by the available V7-V15 residual evidence without at least one of the
following prohibited moves:

- increasing the absolute request cap beyond four;
- weakening genuine-job proof;
- guessing provider/company routes from family detection alone;
- adding company-specific exceptions;
- turning ambiguous API/form/static-asset hints into navigation authority;
- introducing provider/LLM/Tavily side effects into the deterministic layer.

Do not reopen speculative deterministic lanes merely to improve the 40-cohort
score. A future deterministic slice requires genuinely new evidence and must
re-enter through this same fail-closed gate.

## Sole next action

Freeze `23/40` / `17/40` as the deterministic acquisition baseline and hand the
17 unresolved `no_genuine_job_detail` records to task-specific booster admission.
For unusual ATS/source semantics and novel external-information gaps, `#522`
(`LLM-BOOST-001`) remains the LLM/search authority. The parallel ML learning lane
remains active and preserved for repeatable, label-rich surfaces such as
`job_review_relevance`; it is not replaced, demoted, or deleted by this handoff.

No additional deterministic acquisition mutation is currently authorized.
If later ML/LLM or new site evidence identifies a generic deterministic rule, it
must be proposed back into the deterministic layer with focused positive and
negative tests, then validated by a new V4 40-cohort proof followed by a fresh
V16 residual gate.

## Re-entry status

Repository work is active. The old June planning gate is superseded.
Deterministic acquisition hardening for the present cohort is complete at the
current evidence-supported boundary.
