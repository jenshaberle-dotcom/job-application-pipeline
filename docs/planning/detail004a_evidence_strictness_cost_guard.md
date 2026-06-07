# DETAIL-004A Evidence Strictness & Cost Guard

Status: implemented as DETAIL-004 hardening follow-up
Safety zone: SZ2 evidence and gates

## Purpose

DETAIL-004 proved that a structured search provider such as Tavily can find concrete job-detail URLs when static portal probing cannot. The first Tavily smoke also exposed three hardening needs before the result can be applied safely:

1. A search result can redirect to a different employer or source family.
2. A company name can contain the target location and create false location evidence.
3. Search and embedded discovery can produce duplicate URL variants.

DETAIL-004A keeps the Tavily path valuable while making the resulting evidence stricter and cheaper to review.

## Boundary

DETAIL-004A does not expand write permissions. It remains inside the DETAIL-001/DETAIL-004 boundary:

- no candidate URL writes
- no connector registration
- no source activation
- no Bronze/Silver writes
- no scheduler changes
- no raw HTML persistence

Search-provider results remain candidate evidence only. Bounded HTTP validation and gate assessment remain mandatory.

## Rules added

### Final URL domain must remain plausible

If a search-result URL looks plausible but the fetched final URL redirects to a different base domain, the candidate is rejected before supported detail evidence is created.

This prevents evidence from sources such as subsidiary, neighbouring, or unrelated job boards from passing the current candidate's detail gate accidentally.

### Supported details require an accepted URL assessment

A detail page is only persisted as supported evidence when the URL assessment itself is accepted. Matching profile and target terms alone are not enough.

### Employer-brand location suppression

If the company name itself contains a target location, such as Hannover in Hannover Rück, that term does not count as location evidence by itself. It must also appear in a stronger location context, such as:

- the job URL path
- `Standort Hannover`
- `Arbeitsort Hannover`
- `Location Hannover`
- `in Hannover`

This prevents London/Orlando jobs from passing merely because the employer brand contains Hannover.

### Detail URL deduplication

Equivalent detail URLs are deduplicated before validation and before supported evidence output. Slash variants and repeated final URLs should not inflate supported evidence counts.

### Search budget observability

DETAIL-004A adds lightweight budget observability to the evidence payload:

- search provider
- max search queries
- max search results
- requested search query count
- estimated provider credit count for Tavily-style providers

This is an approximation for operational control, not a billing source of truth.

## Expected effect

After DETAIL-004A:

- Tavily can still move candidates past `detail_evidence_gate` when valid detail evidence exists.
- Cross-domain or brand-only evidence should no longer pass.
- Reports should be more trustworthy and easier to review.
- Tavily usage can stay bounded and visible for medium-term free-tier operation.
