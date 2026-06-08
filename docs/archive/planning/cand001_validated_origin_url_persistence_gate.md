# CAND-001 Validated Origin URL Persistence Gate

Status: Planned implementation baseline
Safety zone: SZ1_CANDIDATE_METADATA
Freeze path: active maturity block after EO-002E

## Purpose

CAND-001 closes the gap found by EO-002E:

- EO-002D can select validated origin URLs.
- EO-002E can show that these URLs are not yet persisted in `candidate_url`.
- Downstream gates should not run from report-only URL evidence.

CAND-001 defines the reviewed transition from a live bounded URL-Finder result into `employer_origin_source_candidates.candidate_url`.

## Boundary

CAND-001 may write only candidate metadata under explicit apply mode.

It must not:

- write gate reviews
- write evidence rows
- register connectors
- activate sources
- write Bronze or Silver data
- change scheduler behavior
- weaken gates or Türsteher thresholds

## Source-of-truth rule

URL-Finder JSON exports are review context, not source-of-truth inputs.

A candidate_url write must be based on one of these reviewed inputs:

- a live bounded URL-Finder validation result from the CAND-001 command, or
- a later explicitly reviewed manual URL path, if implemented under the same SZ1 boundary.

This avoids turning local exports into hidden pipeline inputs.

## Default command shape

Dry-run first:

    python -m scripts.run_cand001_validated_origin_url_persistence_gate \
      --benchmark-label cand001_review_YYYYMMDD_HHMM \
      --company-key hannover_ruck \
      --company-key e_on_grid_solutions \
      --target-location Hannover \
      --reviewed-by jens \
      --timeout-seconds 3 \
      --max-url-candidates 4 \
      --search-provider none

Apply only after review:

    python -m scripts.run_cand001_validated_origin_url_persistence_gate \
      --benchmark-label cand001_apply_YYYYMMDD_HHMM \
      --company-key hannover_ruck \
      --company-key e_on_grid_solutions \
      --target-location Hannover \
      --reviewed-by jens \
      --timeout-seconds 3 \
      --max-url-candidates 4 \
      --search-provider none \
      --apply

## Decision taxonomy

| Decision | Meaning |
|---|---|
| persist_validated_candidate_url | A/B-tier live URL-Finder result and empty candidate_url. |
| no_action_already_persisted | Candidate already stores the selected URL. |
| manual_review_required | URL evidence exists but is not strong enough for SZ1 write. |
| manual_review_required_url_conflict | Candidate has a different URL already. |
| manual_review_required_duplicate_url | Another candidate already uses the selected URL. |
| no_selected_url | Live URL-Finder did not select a URL. |
| skip_protected_active_controlled | Candidate is active_controlled and protected by default. |

## Expected next step after CAND-001

After candidate_url is persisted, EO-002E should no longer stop at `candidate_url_persistence` for that candidate. The next maturity step can then inspect detail evidence, gate stops and next-safe-action behavior from the persisted candidate state.
