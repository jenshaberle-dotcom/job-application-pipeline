# F6 — Template-Authoritative Application Drafting

Status: ACTIVE — Slices A/B operator accepted; Slice C released in 1.0.72, operator-selected target hardening in qualification

## Outcome

F6 is the final package of the current frozen Product campaign.

The application workflow may adapt **text only** inside two operator-approved private PDF layouts. The layouts themselves are immutable product authority. Candidate claims remain grounded in approved Candidate Facts and exact current Employer-Origin evidence. Human review is mandatory. F6 grants no automatic submission or send authority.

## Canonical private templates

The PDF bytes remain local/private. Public repository truth stores only their exact binary identities, page geometry and editable-zone contract.

| Document | Template ID | SHA-256 | Geometry |
| --- | --- | --- | --- |
| Application letter | `f6-application-letter-hornetsecurity-2026-09-17-v1` | `e533e27c8bc4ac04b64e29e8d91dcfd134d23af075f76ec179e0d9d0ab1410c8` | 1 page, Letter, 612 x 792 pt |
| CV | `f6-cv-hornetsecurity-2026-09-17-v1` | `8f67040b6ef9248e734a18e46df87fa786f33c3c8f605785baf7ad324432e041` | 2 pages, A4, 595.32 x 841.92 pt each |

Canonical machine-readable authority:

`config/application_templates/f6_template_authority_v1.json`

The mixed page formats are intentional current operator truth. No normalization to A4 or another geometry is authorized.

## Layout boundary

Immutable without a new explicit operator template approval:

- page size and page count;
- portrait/photo placement;
- navy header rules and section rules;
- signature image and its position;
- column/grid geometry;
- panel backgrounds;
- font/layout/spacing geometry outside declared zones.

Only manifest-declared text zones may change. Text overflow must fail closed rather than move graphics, resize the page, reflow into a new design or manufacture an alternate page.

## Content authority

Generated/adapted text may use only:

1. approved Candidate Facts;
2. exact current Employer-Origin vacancy evidence;
3. structural text already present in the approved template when it is not treated as a new candidate claim.

Missing evidence remains missing/unknown. Template text is not independent fact authority.

## Hard-cut regression rule

F6 removes the previous generic document-generation authority. The following legacy paths are physically absent and regression-gated against return:

- retired module basename `product_v1_application_document_export.py`;
- retired module basename `product_v1_application_document_package.py`;
- retired stylesheet basename `application-package-downloads.css`;
- their dedicated generic renderer/package tests.

The retired path created new A4/DOCX documents independent of the approved layouts. It is incompatible with F6 and has no fallback authority.

The browser/CLI intake also no longer accepts arbitrary replacement PDFs. It accepts only an exact F6 hash + page-geometry match. Installing a canonical template supersedes DB authority for the prior approved row and removes older managed upload bytes of that document type.

## Slice A — Template Authority

Status: **COMPLETE / OPERATOR ACCEPTED** on installed 1.0.68. The later 1.0.69 runtime LF hardening did not change F6 template authority.

Acceptance criteria:

- exactly two canonical templates;
- exact binary SHA-256 and page geometry are enforced;
- binaries remain private/local;
- explicit editable zones are public and bounded within their pages;
- arbitrary or visually similar PDFs fail closed;
- Product readiness requires exact template authority, not merely an `approved` DB row;
- old generic renderer/package paths are physically absent;
- Control Center explains the authority and exposes only exact-template verification;
- at Slice A completion, generation could produce grounded review text while rendering was still pending; this historical state is superseded by the accepted Slice-B renderer;
- database/application/submission/send authority remains unchanged.

### Slice A operator evidence

Installed 1.0.68 successfully verified both exact private templates through the Product surface. The generic DOCX/A4 path remained absent. This closes Slice A and authorizes Slice B only; it grants no final PDF export or submission/send authority.

## Slice B — Template-Bound Renderer — COMPLETE / OPERATOR ACCEPTED

PR #999 introduces a new F6-only renderer authority. It is not a revival of the retired generic exporter.

Acceptance criteria:

- exact F6 hash/geometry validation remains the entry gate;
- only manifest-declared text-zone IDs are accepted;
- redaction removes text only and preserves images/vector graphics;
- no automatic font/page scaling is permitted; overflow fails closed;
- every page is raster-compared against its exact source template and all pixels outside declared zones must remain identical;
- evidence contains source/output hashes and per-page outside-zone pixel hashes/counts;
- rendered bytes remain review-only and grant no application/submission/send authority;
- CI uses synthetic PDFs only; private template bytes remain local.

### Slice B operator evidence

Installed Product **1.0.71** on exact release source `a7eae418cbcc8c901070d9db65505cece086e6f7` completed the real private-template qualification successfully.

The local proof covered exactly both canonical templates (`template_count: 2`). The application-letter render changed only `body.paragraph_1`; the CV render changed only `p1.short_profile`. Every page reported `outside_zone_pixel_identity: true` and `changed_pixels: 0` outside declared zones. Rendered PDFs were not persisted and private template paths/bytes were not disclosed. The qualifier reported zero database reads/writes, provider/network requests, application actions, submission actions and send actions, and ended with `F6_TEMPLATE_RENDERER_QUALIFICATION=PASS`.

This closes Slice B and authorizes Slice C only. It does not grant draft approval, application, submission or send authority.

## Slice C — Review/Edit + Local PDF Export — IN QUALIFICATION

The first Slice-C implementation shipped as **1.0.72** from exact source `f55b8adab62337b4e0a28c3ad9bcb56186c84cc6`. It provides manifest-zone editing, source-manifest-bound local PDF rendering and the accepted Slice-B outside-zone pixel proof.

The first installed operator attempt exposed a separate pre-existing Product coupling before the new PDF surface could be exercised: the Application Workspace accepted only `gold_product_v1_top_jobs` targets while current Product truth contained **0 rankable / 0 Top-5** rows.

### Runtime diagnosis — 2026-09-24

The installed Product payload reported 80 current active jobs and 45 authoritative Affinity rows, but zero rankable jobs. Its readiness population was dominated by `hard_filter_evidence_required` plus `assessment_required`; VALUNY Silver 613 was active, Origin-validated and Affinity-authoritative while its hard-filter state remained unknown.

A separate verified RCC warm-runtime read-only proof confirmed the population-level condition without mutating authority: rankable `0`, Top-5 `0`, 65 hard-filter-evidence-required rows, 13 assessment-required rows and 2 blocked hard-filter rows. Capability Fit remained unknown for the highest-Affinity blocked rows. This is consistent with the existing PD-053/054/059 fail-closed Product contract and must not be repaired by manufacturing ranking authority.

Refresh is not a ranking/materialization action. Repeating UI refresh cannot legitimately turn unknown Fit/hard-filter evidence into Top-5 truth.

### Operator-selected drafting boundary

Candidate target: **1.0.73** on `feature/f6-c-operator-selected-target`.

F6 drafting and Top-5 recommendation authority are now separated deliberately:

- Top-5 remains unchanged and fail-closed. No row is promoted, ranked or threshold-bypassed for F6.
- An operator may explicitly select a **current, Origin-validated, authorized employer-origin job** as a review-drafting target even when it is not Top-5.
- An operator-selected target carries `authority_source=operator_selected_current_job` and **no Product rank**.
- An unknown hard-filter state remains unknown; drafting does not convert it to passed.
- A known hard-filter failure remains blocked from this path.
- Candidate claims still come only from approved Candidate Facts and exact current vacancy evidence.
- Exact F6 template/hash/zone authority, source-manifest binding, overflow fail-closed and outside-zone pixel identity remain unchanged.
- Drafting remains review-only: no application, submission, send or Product/ranking authority is created.

This boundary matches the real operator workflow: a recommendation system may honestly have an empty Top-5 while the operator can still decide to prepare material for a specific current vacancy.

### Slice-C rendering contract

- Control Center loads the two exact locally installed private templates and exposes only their manifest-declared text zones;
- source text from each declared zone is visible as the editable baseline; no undeclared page area is editable;
- explicit operator action may apply bounded draft suggestions: CV summary -> `p1.short_profile`; letter opening/fit/closing -> declared letter body zones;
- the operator can edit those zone texts before rendering;
- export is bound to the exact draft `source_manifest_sha256`; if the current job/fact/template context drifts, export fails closed and requires draft regeneration;
- final rendering delegates to the accepted Slice-B renderer, including overflow fail-closed and outside-zone pixel-identity proof;
- unchanged documents may be exported as their exact source-template bytes; changed documents carry renderer evidence and output SHA-256;
- rendered PDFs cross only the loopback Product boundary as base64 and become local browser/WebView PDF objects for explicit Open/Download actions; no public/cloud persistence is introduced;
- human review remains mandatory and no automatic submit/send authority exists.

### Next operator gate

After exact-head CI and immutable **1.0.73** release:

1. update through the integrated JAP updater and verify the exact 1.0.73 source;
2. in **All jobs**, select VALUNY `Machine Learning Engineer / Data Scientist (m/w/d)` (Silver 613) or another current non-failed Employer-Origin job;
3. press **Prepare application** and verify the workspace labels it **Operator-selected current job** rather than inventing a Top-5 rank;
4. generate grounded review text;
5. apply/edit only the permitted F6 text zones;
6. press **Render local PDFs** and require `Outside-zone identity PASS` for each changed document;
7. open/download both PDFs and visually confirm that approved layouts remain intact and only intended text zones changed.

Any known hard-filter failure, source/context drift, overflow, unexpected layout change or missing pixel proof remains fail-closed.

## Explicit non-goals

- no alternate template chooser;
- no free-form layout generation;
- no DOCX as template authority;
- no automatic page reflow;
- no automatic application submit;
- no automatic email send;
- no silent replacement of the canonical templates.
