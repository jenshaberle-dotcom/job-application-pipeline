# Finanz Informatik Origin Path Review — S2H

## Purpose

S2H documents the manual Finanz Informatik origin-path review after the S2G active source-target decision.

The goal is not to build a connector yet. The goal is to decide whether Finanz Informatik exposes a clean, bounded and defensible employer-origin or ATS-near acquisition path that is worth a later source-target spike.

## Decision Signal

The Finanz Informatik origin path appears technically viable enough for a later bounded source-target spike.

The current evidence does not indicate a duplicate-heavy link set. The link snapshot and relevance triage show that the main issue is not duplicate noise, but relevance and scope control.

## Evidence Summary

The S2H export artifacts were written under:

    exports/s2h_finanz_informatik_origin_path_review/

The relevance triage found:

- 558 unique links were triaged.
- 216 links were classified as origin open-position candidates.
- 186 links were classified as OnApply detail candidates.
- 16 links were classified as strong candidates for a relevance probe.
- 33 links matched the profile but need location review.
- 52 links were excluded as training, dual-study, working-student or entry-level signals.

## Greenhouse Lesson Applied

The Greenhouse history showed that broad, weakly differentiated ingestion can create historical burden and low-value hot-store volume.

Therefore, Finanz Informatik must not be ingested as a broad "all jobs" source.

A future Finanz Informatik source-target spike must start with relevance gates, not with maximum collection volume.

## Required Relevance Gates Before Any Connector Work

A future spike should explicitly separate:

- `/de/karriere/offene-stellen/...` from career overview pages
- normal open positions from `duales-studium-ausbildung`
- professional roles from working-student, trainee and Ausbildung roles
- Hannover or remote/Germany-relevant jobs from Frankfurt/Muenster-only jobs
- Data / BI / Analytics / Engineering / Product-adjacent roles from unrelated IT or management roles

## Interpretation

Finanz Informatik is not a duplicate-noise problem.

The source path appears rich and structured enough to justify a later bounded spike, but the source contains many roles that are not automatically relevant to the project scope.

The main risk is false-positive ingestion:

- training and dual-study roles
- working-student roles
- trainee roles
- non-target locations
- general IT or management roles outside the intended search scope

This makes Finanz Informatik useful as a controlled source-target candidate, but only if relevance filtering is part of the design from the beginning.

## Recommendation

Finanz Informatik is viable enough for a bounded read-only source-target spike, but only with strict relevance gates and explicit exclusion logic.

Recommended next block:

    S2I — Finanz Informatik bounded source-target spike design

S2I should define:

- exact source URL(s)
- allowed URL patterns
- excluded URL patterns
- relevance gate rules
- maximum request count
- raw record shape
- evidence fields
- dry-run/export-first behavior
- stop conditions

## Non-Goals

S2H does not approve a production connector.

S2H does not approve broad ingestion of all Finanz Informatik jobs.

S2H does not approve arbitrary crawling.

S2H does not approve detail-page fetching without a separately documented boundary.

S2H does not treat OnApply links as automatically allowed or sufficient.

S2H does not bypass manual review of acquisition path and usage boundaries.
