# Finanz Informatik Export-First Spike — S2J

## Purpose

S2J implements the first bounded Finanz Informatik source-target spike as a read-only export-first workflow.

The goal is not to build a production connector. The goal is to test whether the S2I URL and relevance gates can produce reviewable candidate evidence before any Bronze persistence or connector decision is made.

## Script

S2J adds:

    python -m scripts.preview_finanz_informatik_source_target_spike

The script reads explicitly configured source URLs, extracts candidate links, applies URL and relevance gates and writes review artifacts under:

    exports/s2j_finanz_informatik_export_first_spike/

## Boundaries

S2J does not:

- write to the database
- fetch job detail pages
- implement a connector
- activate a source target
- store raw HTML
- crawl arbitrary pages
- approve OnApply usage
- approve Bronze persistence

## Implemented Gates

The spike classifies links into path classes such as:

- origin open-position candidate
- OnApply detail candidate for manual review only
- training or dual-study exclusion
- career content or overview
- external non-job link

It also applies relevance signals for:

- Hannover / remote / Germany-wide relevance
- Data / Analytics / BI / SQL / Python / AI / Data Governance / Data Platform
- training, dual-study, working-student, trainee and similar exclusion terms

Secondary locations such as Frankfurt or Muenster are not treated as positive review candidates unless a remote, Germany-wide or target-location signal is visible at listing level. This applies both to profile matches and to low-profile job-path candidates, keeping possible remote assumptions from creating review burden.

## Output Files

The script exports:

- `finanz_informatik_spike_candidates.csv`
- `finanz_informatik_spike_relevance_summary.csv`
- `finanz_informatik_spike_manifest.json`
- `finanz_informatik_spike_review.md`

The manifest explicitly records:

- no database writes
- no detail pages fetched
- no raw HTML persisted
- no connector implemented
- no source target activated

## Interpretation Boundary

Positive S2J rows are review candidates only.

A strong listing candidate means that a URL passed the listing-level gates. It does not mean that the job is relevant enough for Bronze persistence. Detail evidence may still be required in a later separately bounded step.

OnApply detail links are treated as manual-review-only evidence. They are not automatically approved for crawling or ingestion.

## Greenhouse Lesson Applied

S2J continues the Greenhouse lesson:

    source volume is not source value

The spike intentionally avoids all-job ingestion. It tests whether a high-signal subset can be identified before any persistence decision.

## Next Step

The next step is to run S2J and review the exported artifacts.

Only after reviewing the export should the project decide whether to:

- add a separately bounded detail-page probe
- defer Finanz Informatik because listing-level evidence is insufficient
- design a connector candidate with explicit Bronze persistence constraints
- shift back to Silver-gate or search-term quality work
