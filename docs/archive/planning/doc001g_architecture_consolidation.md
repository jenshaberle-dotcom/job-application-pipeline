# DOC-001G Architecture Consolidation

Status: implemented documentation build log
Scope: architecture reader path, current diagrams, README motivation repair
Date: 2026-06-08

## Purpose

DOC-001G consolidates the architecture documentation after DOC-001F.

The goal is not to create another long planning note. The goal is to make the
active architecture path easier to read and harder to confuse with older
Search-Intelligence narratives.

## Changes

- Restored a portfolio-readable project motivation in `README.md`.
- Kept the README concise, but less sterile and more aligned with the actual
  career/search-intelligence motivation.
- Rebuilt `docs/current/system-diagrams.md` around the current end-to-end
  Search Intelligence control surface.
- Added learning and repair-loop diagrams.
- Added `docs/archive/documentation-rebaseline/architecture_document_status.md` as the control
  surface for architecture document authority.
- Updated `docs/architecture/README.md`, `docs/README.md`, and
  `docs/archive/documentation-rebaseline/current_truth_documentation_map.md` to include the new
  status surface.
- Marked older Search Intelligence architecture narratives as not-primary after
  DOC-001G.

## Corporate design interpretation

DOC-001G keeps the Deep Ocean / Ocean Deep identity, but as maintainable
architecture documentation:

- Mermaid diagrams over heavy image assets.
- Sonar/signal/depth/control-surface language where it clarifies the system.
- Calm technical product language instead of gaming or decorative metaphors.
- GitHub-readable Markdown first.

## Non-goals

- No ADR reclassification pass yet.
- No mass file moves.
- No pipeline logic changes.
- No new source/connector expansion.

## Follow-up

- DOC-001H: ADR status classification pass.
- DOC-001I/J: selective deprecation markers or archive moves for remaining old
  architecture/planning/source-analysis docs.
- Move old README architecture-contract anchors toward Current Truth docs and
  tests once the rebaseline is stable.
