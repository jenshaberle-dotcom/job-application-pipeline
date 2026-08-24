# ATS API Acquisition Strategy

Status: active reference for `ACQ-RUNTIME-001` Slice 3
Date: 2026-08-24

## Purpose

This document defines where API/feed acquisition belongs in the employer-origin
acquisition stack after the static deterministic surface was exhausted and runtime
network observation proved useful.

The objective is not to invent provider routes from an ATS label. The objective is
to promote **documented public job interfaces** or **repeatedly observed runtime
protocols** into bounded provider-family adapters only after employer/tenant/board
authority is established deterministically.

## Current repository truth

The project already has API/feed precedents:

- Greenhouse is implemented through its public board API at
  `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs`.
- Personio selected targets are implemented through public XML job feeds.
- Bundesagentur fuer Arbeit is an official public job API source.
- `src/search_intelligence/ats_provider_registry.py` recognizes Greenhouse,
  Personio, Workday, SuccessFactors, SmartRecruiters, Lever, Ashby, Recruitee,
  Workable, softgarden, d.vinci, Onlyfy, JOIN and other ATS families.

Provider recognition is intentionally weaker than tenant/employer authority.
`ATSProviderRecognition` explicitly grants neither `tenant_authority` nor
`delegation_permitted` nor `product_authority`.

## External interface check — 2026-08-24

Current provider documentation confirms several useful machine-readable public
interfaces:

| Provider | Public job interface | Acquisition assessment |
|---|---|---|
| Greenhouse | Job Board API | already implemented; preferred when board token is proven |
| Personio | public XML feed at `{account}.jobs.personio.com/xml` when enabled | already implemented for selected targets; deterministic feed candidate |
| Lever | Postings API, including global and EU endpoints | strong provider-family adapter candidate once site identity is proven |
| Ashby | public Job Postings API under `/posting-api/job-board/{JOB_BOARD_NAME}` | strong provider-family adapter candidate once board name is proven |
| SmartRecruiters | public Posting API under `/v1/companies/{companyIdentifier}/postings` | strong provider-family adapter candidate once company identifier is proven |
| Recruitee | public careers-site API is documented | candidate after concrete residual evidence |
| Workday | no project-authorized general public jobs API contract | treat observed CXS/runtime requests as protocol evidence; do not invent tenant routes |
| JOIN | public job inventory is observable in current residual evidence, but no generic project-authorized API route exists yet | promote only from explicit employer/runtime delegation evidence |

External references used for this assessment:

- Lever Postings API: `https://github.com/lever/postings-api`
- Ashby Job Postings API: `https://developers.ashbyhq.com/docs/public-job-posting-api`
- SmartRecruiters Posting API: `https://developers.smartrecruiters.com/docs/posting-api`
- Personio XML job integration: `https://support.personio.de/hc/de/articles/207576365`

## Admission rule

A provider-family API/feed adapter may run only when all applicable authority
steps succeed:

1. **Employer authority** — the originating career surface belongs to the expected
   employer under the existing deterministic authority rules.
2. **Provider evidence** — the provider family is observed, not guessed.
3. **Tenant/board identity evidence** — the required provider identifier (board
   token, site name, company identifier, tenant, job-board name, etc.) is observed
   from an employer-authorized page, redirect, structured state, public widget,
   or authorized runtime transaction.
4. **Route contract** — the route is either documented by the provider as a public
   job interface or has repeated cross-company runtime evidence sufficient for a
   separately tested protocol adapter.
5. **Bounded request policy** — explicit time/request/page/result caps apply.
6. **Job-record proof** — returned records must satisfy the fail-closed runtime job
   record contract or produce candidate detail URLs that pass existing genuine-job
   proof. API transport by itself is never genuine-job authority.
7. **No authority escalation from provider detection alone** — knowing that a page
   uses Workday, Lever, SmartRecruiters, etc. never permits guessing a tenant or
   endpoint.

## Preferred acquisition order

For a provider-recognized employer target, prefer the least expensive structured
surface that is already authorized:

`documented public API/feed -> observed stable provider protocol -> bounded browser runtime -> search/LLM booster`

This ordering is acquisition-specific. It does not change the global ML/LLM
admission policy for other tasks.

The browser remains useful even when an API adapter exists because it can prove the
board/tenant identifier and explicit delegation needed to authorize that adapter.
Once a stable public/API protocol is proven, subsequent acquisition should avoid
paying the browser cost when direct structured retrieval can preserve the same
truth boundary.

## ACQ-RUNTIME-001 residual implications

Current runtime evidence already demonstrates why this split matters:

- **Clarios / Workday:** browser runtime exposed structured Workday inventory that
  static HTML did not. This is a protocol-promotion candidate, not authority to
  hard-code a guessed Workday CXS path.
- **TrustYou / JOIN:** runtime observation produced genuine JOIN job detail URLs;
  the remaining question is deterministic one-hop inventory delegation.
- **AOK Niedersachsen:** runtime observation found a same-host detail URL, so no
  provider API is needed for that rescue.

The remaining cohort should therefore be classified after the next V18 shadow by
provider family and available tenant/board evidence. Public API adapters should be
implemented only for provider families actually represented by unresolved cases or
for already-supported source families where the adapter is independently valuable.

## Slice-3 implementation rule

After V18:

1. group unresolved cases by provider family;
2. record which cases contain deterministic tenant/board identifiers;
3. classify each provider as `documented_public_interface`,
   `observed_runtime_protocol`, or `no_authorized_structured_route`;
4. implement the highest-reuse adapter first;
5. require focused positive, negative and cross-tenant authority tests;
6. run a fresh bounded residual shadow before changing default acquisition;
7. if promoted into deterministic default acquisition, run a new 40-cohort V4
   proof followed by fresh residual evidence.

## Hard boundaries

- no credentialed customer APIs for public job acquisition unless separately
  authorized and justified;
- no application-submission APIs in acquisition discovery;
- no provider/company exceptions merely to improve the 40-cohort score;
- no guessed board tokens, tenant names, site names or company identifiers;
- no raw API response persistence by default;
- no cookie/token/auth-header/form-value persistence;
- no DB/Product/source/application mutation in shadow evaluation;
- provider API output remains evidence subject to deterministic authority.

## Decision

API/feed acquisition is a **first-class deterministic optimization path**, not a
replacement for runtime observation. Public ATS interfaces can materially reduce
browser cost and improve stability once their target identity is proven. Dynamic
or undocumented ATS families such as the currently observed Workday case should
first be learned from bounded runtime network evidence and only then promoted into
provider-family protocol adapters.
