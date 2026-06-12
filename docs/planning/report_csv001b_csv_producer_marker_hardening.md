# REPORT-CSV-001B CSV Producer Marker & Reference Hardening

Status: Planned follow-up

## Context

REPORT-CSV-001 established the hard boundary that CSV/Excel/local export artifacts must remain review outputs only and must not become pipeline, gate, apply, benchmark, candidate-creation, or production/cloud inputs.

Current REPORT-CSV-001 baseline:

- Total CSV references scanned: 109
- Forbidden CSV reads from exports/: 0
- Unmarked CSV export producer/reference locations: 18
- Current enforcement mode: strict_unmarked_exports=False

The 109 CSV references are intentionally broad scan coverage and include filenames, writers, tests, documentation references, and scanner/test fixtures. They are not all defects. The 18 unmarked export producer/reference locations remain cleanup debt.

## Goal

- Mark CSV export producers and references explicitly as review_output_only_not_pipeline_input.
- Add filename, header, manifest, or report metadata markers where appropriate.
- Reduce noisy or false-positive CSV references where sensible without weakening coverage.
- Update docs and tests so future readers understand which CSVs are review outputs only.
- Consider strict_unmarked_exports=True only after producer marking is complete and stable.

## Non-goals

- Do not reintroduce CSV, Excel, Markdown, JSON, or local exports as pipeline inputs.
- Do not use exports as candidate-creation, gate, apply, benchmark, or activation inputs.
- Do not change Candidate Creation, gate logic, connector activation, scheduler semantics, Bronze/Silver/Gold behavior, or database mutation behavior in this cleanup.
- Do not break legacy review exports blindly; harden them incrementally.

## Suggested implementation path

1. Classify the 18 unmarked export producer/reference locations.
2. Add explicit review_output_only_not_pipeline_input markers to filenames, headers, manifests, or adjacent report metadata.
3. Update docs and tests for marked producer expectations.
4. Rerun REPORT-CSV-001 and verify forbidden export reads remain 0.
5. Only after the marker baseline is clean, evaluate stricter enforcement.

## Acceptance criteria

- disallowed_export_csv_read_count remains 0.
- unmarked_export_csv_reference_count trends to 0 or all remaining exceptions are documented.
- No export artifact is consumed as pipeline input.
- Validation remains green.
