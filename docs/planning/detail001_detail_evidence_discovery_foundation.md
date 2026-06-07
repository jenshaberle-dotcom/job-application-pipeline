# DETAIL-001 Detail Evidence Discovery Foundation

Status: implemented as bounded plan/apply foundation
Safety zone: SZ2 evidence and gates

## Purpose

DETAIL-001 closes the next validated gap after CAND-001 and GATE-001:

1. `candidate_url` is persisted under the SZ1 CAND-001 boundary.
2. Initial gates are passed by GATE-001:
   - `source_discovery`
   - `technical_reachability_gate`
   - `risk_gate`
3. The pipeline now needs concrete job/detail evidence before connector-candidate evaluation can continue.

The block makes that transition explicit instead of repeatedly looping on URL persistence or initial gates.

## Boundary

DETAIL-001 may only write, in explicit `--apply` mode:

- rows in `employer_origin_job_detail_evidence` for supported bounded detail evidence
- the `detail_evidence_gate` review/event state

It must not write:

- candidate URLs
- connector registrations
- source activation state
- scheduler configuration
- Bronze/Silver jobs
- raw HTML

Dry-run is the default. Apply requires bounded probing; `--apply --no-probe` is blocked.

## Gate contract

A candidate can pass `detail_evidence_gate` when at least one bounded detail page provides:

- reachable HTTP result
- profile evidence, such as Data, Analytics, SQL, Product Owner, Software, or configured profile terms
- target-location or remote/Germany evidence, such as Hannover, Remote, Deutschland, bundesweit, or configured location terms

If concrete detail candidates exist but cannot validate both signal groups, DETAIL-001 records a manual-review implementation gap. If no detail candidates are found within the bounded budget, it records a manual-review discovery gap.

## CLI

Dry-run for the two current GATE-001 candidates:

    python -m scripts.run_detail001_detail_evidence_discovery \
      --benchmark-label detail001_after_gate001_dry_run \
      --company-key hannover_ruck \
      --company-key e_on_grid_solutions \
      --target-location hannover

Apply after reviewing the exported JSON/Markdown report:

    python -m scripts.run_detail001_detail_evidence_discovery \
      --benchmark-label detail001_after_gate001_apply \
      --company-key hannover_ruck \
      --company-key e_on_grid_solutions \
      --target-location hannover \
      --apply

Reports are written to:

    exports/detail001_detail_evidence_discovery/

## Expected downstream effect

After DETAIL-001 apply:

- Candidates with supported evidence should move past the `detail_evidence_gate` blocker.
- EO-002E should no longer recommend `run_detail_evidence_discovery_plan` for those passed candidates.
- The next safe action should shift toward connector-candidate evaluation or manual review, depending on the evidence result.

## Freeze/Maturity note

This is not a new architecture expansion. It is the next missing contract in the already validated chain:

URL-Finder → CAND-001 → GATE-001 → DETAIL-001 → Connector Candidate.
