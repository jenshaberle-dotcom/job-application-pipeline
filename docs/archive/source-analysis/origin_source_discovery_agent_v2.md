# Origin Source Discovery Agent v2 — Search-backed Provider Chain

## Purpose

Version 2 turns the origin-source discovery foundation into a search-backed agent. The agent must not rely on URL guessing as the primary strategy. It should use evidence in this order:

1. Existing market evidence and persisted candidate context.
2. Optional web-search provider results for queries such as `"Company" Karriere Jobs`.
3. Known ATS/provider-domain patterns when search-result context confirms company identity.
4. Deterministic URL heuristics as a bounded fallback only.

The goal is performance through better evidence, not through more aggressive guessing.

## Boundary

The agent remains read-only:

- no `candidate_url` write
- no connector registration
- no source activation
- no Bronze/Silver write
- no scheduler change
- no automatic gate mutation

Any future URL assignment must remain a separate dry-run/apply step.

## Provider chain

The script supports optional providers:

- `--search-provider none` (default): no external API calls
- `--search-provider tavily`: uses `TAVILY_API_KEY`
- `--search-provider brave`: uses `BRAVE_SEARCH_API_KEY`
- `--search-provider google_cse`: uses `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_CX`
- `--search-results-json`: offline replay input for validation without external calls

Providers can be repeated. If `none` is combined with a real provider, the real provider wins.

## Scoring change

Search results are not accepted blindly. A search result can strengthen a candidate only when the result title/snippet/query contains company identity evidence. This allows provider-hosted ATS pages to be considered without accepting unrelated generic job portals.

Examples:

- `jobs.hannover.de` for `Hannover Rück SE` remains rejected when the context only indicates the city/region Hannover.
- A Workday/ATS URL can be accepted when the search result context contains `Hannover Rück` and the page is reachable/career-like.
- `grid.de` remains weak for `E.ON Grid Solutions` unless search/provider context strongly links it to the company.

## Operational use

Recommended first benchmark:

```bash
python -m scripts.run_origin_source_discovery_agent \
  --company-key technische_informationsbibliothek_tib \
  --company-key ivv \
  --company-key wertgarantie \
  --company-key genoverband_e_v \
  --company-key x1f \
  --company-key materna_information_communications \
  --company-key msg_systems \
  --company-key hannover_ruck \
  --company-key e_on_grid_solutions \
  --target-location Hannover \
  --search-provider tavily \
  --search-query-limit 4 \
  --search-max-results 5
```

For API-free validation, use `--search-results-json` with a replay file shaped either as a list of result objects or a mapping from `company_key` to result lists.

## Decision principle

A good outcome is not always `origin_url_candidate_selected`. A correct `not_found` or `manual_review_required` is better than poisoning `candidate_url` with a plausible-looking but unrelated domain.
