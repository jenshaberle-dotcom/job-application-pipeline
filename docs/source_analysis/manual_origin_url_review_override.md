# S7M Manual Origin URL Review Override

## Purpose

The Origin Source Discovery Gate must not invent or guess employer-origin URLs.
If no trusted URL evidence exists, the candidate remains in manual review. This
block adds a controlled human-in-the-loop override for cases where a reviewer has
verified a plausible origin/career URL outside the automated evidence set.

## Boundary

Manual URL input is not a shortcut around safety policy. A reviewer-provided URL
runs through the same URL assessment rules as persisted evidence:

- HTTPS is required.
- private hosts, localhost, unsupported schemes and malformed URLs are rejected.
- known aggregators such as StepStone, LinkedIn, Indeed, XING and Glassdoor are
  rejected as origin URLs.
- career/job-board-like paths are preferred for automatic assignment.
- homepage-only or unclear URLs remain manual-review evidence, not connector-ready
  origin sources.

The override only updates source-discovery evidence and, when safe enough, the
`candidate_url` field on the candidate record. It does not register a connector,
activate a source, write Bronze data or change schedules.

## Example

Dry-run first:

```bash
python -m scripts.run_origin_source_discovery_gate_agent \
  --company-key deutsche_bahn \
  --manual-origin-url "https://db.jobs/de-de/jobs" \
  --reviewed-by jens
```

Persist only after the dry-run shows a selected low-risk URL and an assignment
candidate result:

```bash
python -m scripts.run_origin_source_discovery_gate_agent \
  --company-key deutsche_bahn \
  --manual-origin-url "https://db.jobs/de-de/jobs" \
  --reviewed-by jens \
  --write
```

## Product Rationale

This avoids replacing manual job search with an approval hell. The system remains
defensive where evidence is weak, but it provides a clean, audited path for human
judgement when the automated discovery gate cannot find a safe URL on its own.
