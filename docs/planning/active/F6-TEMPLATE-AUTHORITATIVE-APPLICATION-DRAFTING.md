# F6 — Template-Authoritative Application Drafting

Status: ACTIVE — Slice A template authority hard cut in qualification

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

- `src/search_intelligence/product_v1_application_document_export.py`;
- `src/search_intelligence/product_v1_application_document_package.py`;
- `frontend/control-center/src/application-package-downloads.css`;
- their dedicated generic renderer/package tests.

The retired path created new A4/DOCX documents independent of the approved layouts. It is incompatible with F6 and has no fallback authority.

The browser/CLI intake also no longer accepts arbitrary replacement PDFs. It accepts only an exact F6 hash + page-geometry match. Installing a canonical template supersedes DB authority for the prior approved row and removes older managed upload bytes of that document type.

## Slice A — Template Authority

Acceptance criteria:

- exactly two canonical templates;
- exact binary SHA-256 and page geometry are enforced;
- binaries remain private/local;
- explicit editable zones are public and bounded within their pages;
- arbitrary or visually similar PDFs fail closed;
- Product readiness requires exact template authority, not merely an `approved` DB row;
- old generic renderer/package paths are physically absent;
- Control Center explains the authority and exposes only exact-template verification;
- generation can still produce grounded review text, but rendering remains `template_bound_renderer_pending`;
- database/application/submission/send authority remains unchanged.

### Next operator gate

After exact-head qualification, merge and immutable Windows release:

1. update the installed JAP Control Center through the integrated updater;
2. open **Application**;
3. install/verify the exact private CV and application-letter PDFs;
4. confirm both show exact F6 authority/ready;
5. confirm an arbitrary/older PDF is rejected if a negative check is needed;
6. open one current Top-5 target and verify the workspace reaches grounded review-text readiness while **no generic DOCX/A4 download path exists**.

No provider-generated final PDF is required for Slice A.

## Slice B — queued after Slice A operator acceptance

Build the template-bound renderer that edits only declared text zones and preserves the frozen pages pixel-for-pixel outside those zones. It must produce visual-diff evidence against the source templates and fail closed on text overflow.

## Slice C — queued

Control Center review/edit surface for permitted text zones plus final local PDF export. Human acceptance remains mandatory.

## Explicit non-goals

- no alternate template chooser;
- no free-form layout generation;
- no DOCX as template authority;
- no automatic page reflow;
- no automatic application submit;
- no automatic email send;
- no silent replacement of the canonical templates.
