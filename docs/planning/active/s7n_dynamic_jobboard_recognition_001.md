# S7N-DYNAMIC-JOBBOARD-RECOGNITION-001

Status: implementation validation  
Issue: #393  
Parent runtime acceptance: #392

## Runtime evidence

Exact no-write S7N probes reached both Accompio and Computacenter with HTTP 200,
but classified each as `no_structural_job_evidence`. Both had career-context
signals and no persisted feasibility review was created.

Independent review showed that current job inventory exists behind both employer
career surfaces. The equal terminal result therefore exposed a generic evidence
projection gap rather than two proven product stops.

## Root cause

The historical connector-feasibility module already contains bounded HTML-level
structure detection, but the active evaluator used only classified anchor counts.
Dynamic boards whose initial HTML exposes search, schema or job-list structure
without server-rendered detail anchors therefore collapsed to zero.

The anchor classifier also required path-heavy job URLs. A strong link such as
`Offene Stellen` could remain career context when it pointed to a trusted career
subdomain with only a locale path such as `/de`.

## Implementation

The active S7N runner now uses a small runtime completion layer that preserves the
historical contract as authority and adds only two missing evidence projections:

1. combine existing HTML structural detection with classified link evidence for
   trusted job/career contexts;
2. surface strong, safe delegated job-board links as reviewable URL-repair
   candidates.

The completion layer does not replace URL safety, bounded fetch, legacy link
classification, persistence, queue or downstream build logic.

## Decision preservation

Dynamic HTML structure alone can produce only:

```text
manual_review_required
structural_evidence_without_job_detail
```

It cannot produce `likely_feasible`. Concrete job-detail candidate evidence remains
mandatory for `continue_to_connector_build_planning`.

A delegated board produces only:

```text
manual_review_required
origin_url_repair_candidate_detected
```

It does not select or persist a replacement URL. CAND-001 remains the sole URL
persistence authority.

## Trust boundary

A delegated candidate must satisfy all of the following:

- public HTTPS URL;
- not a known aggregator, social domain, asset or technical endpoint;
- strong job-board label such as `Offene Stellen`, `Stellenangebote`, `Search jobs`,
  `View jobs`, `Vacancies` or a bounded equivalent;
- same registered domain or clearly job/career-oriented hostname;
- job/search path or shallow locale path.

Company names, candidate IDs and known employer URLs are not used for control flow.

## Tests

Direct contract tests cover:

- dynamic job-search HTML without detail links remains manual review;
- a strong delegated-board label surfaces a repair candidate;
- generic `/search/` paths are recognized;
- a job-themed lookalike on an unrelated hostname is rejected;
- concrete job-detail evidence still reaches `likely_feasible`.

## Boundary

This slice authorizes no:

- provider or LLM request;
- database migration or runtime write;
- connector artifact generation, registration or activation;
- Bronze, Silver or Gold job mutation;
- scheduler or Wave change;
- assessment, ranking, Top-5, Candidate Fact or application mutation.

## Runtime acceptance

After CI and merge, repeat the exact Accompio and Computacenter no-write probes from
#392. Review persistence, Accompio URL repair and any connector build remain separate
operator decisions.