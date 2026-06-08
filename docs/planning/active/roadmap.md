# Active Roadmap

Status: active planning
Last rebaseline: DOC-001M

This file is the active roadmap. It is intentionally short. Historical phase
checklists and build notes live in `../archive/planning/` and Git history.

## Current freeze path

| Order | Block | Status | Purpose |
|---|---|---|---|
| 1 | GOV-001 Agent Governance Foundation | done | Make agent-like behavior explicit and reviewable. |
| 2 | DOC-001A-K Documentation Rebaseline Foundations | done | Inventory, current-truth navigation, archive/deprecation, README/runbook, diagrams, DB/docs control and ADR status. |
| 3 | DOC-001L Documentation Information Architecture | done | Restructure docs into current/guides/reference/decisions/planning/archive. |
| 4 | DOC-001M Artifact Consolidation | current | Reduce redundancy, keep active docs lean and prevent a new documentation monster. |
| 5 | STOP-002 Stop Taxonomy & Repair Strategy Registry | next | Make stops, repair paths and next safe actions easier to reason about and operate. |
| 6 | EO/Search Intelligence return path | next | Resume StepStone discovery, promotion quality and URL/detail evidence generics after the maturity baseline is stable. |

## Current product priorities

| Area | Current focus |
|---|---|
| Documentation | Keep current truth small and archive historical build traces. |
| Governance | Keep agent permissions, capability boundaries and drift checks active. |
| Stop/repair logic | Build a clearer taxonomy before adding more UI actions. |
| StepStone discovery | Prove that discovery waves produce new-company yield instead of known-company repetition. |
| Candidate promotion | Improve the Türsteher with measured downstream outcomes, not blind gate weakening. |
| URL/detail evidence | Improve generic discovery and evidence quality without uncontrolled crawling. |
| Control Center | Make review-required states actionable only after stop/repair responsibilities are clear. |

## Architecture freeze rule

<!-- ARCH-001-SAFETY-SECURITY-STATE:START -->
ARCH-001 remains active. New changes must preserve safety, security, data
integrity and explicit state transitions. Opportunistic scope expansion should go
to the backlog unless it improves safety, diagnosis, generics or product maturity
by a clearly meaningful amount.
<!-- ARCH-001-SAFETY-SECURITY-STATE:END -->

## Backlog parking lot

Use the White-Whale backlog for valuable ideas that are not part of the current
maturity path. Saving an idea is not the same as implementing it now.

## Contract anchors

These anchors are intentionally kept because repository tests use the active roadmap
as a lightweight governance and repair-contract surface. They are short by design:
historical implementation detail belongs in the archive, not in the active roadmap.

### DOC-001 Governance Foundation Gate

DOC-001 remains the documentation/governance freeze path that protects the project
from documentation drift while the Search Intelligence product continues to evolve.

### DOC-002 Documentation Drift Baseline

DOC-002 remains the baseline that protects the project from silent documentation
drift. It keeps documentation changes tied to architecture, governance, and
implementation reality instead of becoming detached project prose.

### EO-002B Candidate Reprocessing & URL Finder Validation

EO-002B remains the active contract anchor for candidate reprocessing and URL-finder
validation. The detailed historical plan lives in the archive, but this roadmap keeps
the anchor visible because candidate reset/reprocess and URL-recovery safety remain
important product constraints.

### EO-002D-ROADMAP

EO-002D remains the active reference point for bounded origin-source discovery and
URL-finder repair work. Its detailed historical plan lives in the archive, but the
active roadmap keeps this anchor so repair boundaries stay visible.

