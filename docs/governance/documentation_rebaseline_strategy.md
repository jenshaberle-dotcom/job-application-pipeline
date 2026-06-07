# DOC-001 Documentation Rebaseline Strategy

Status: current governance strategy  
Scope: documentation inventory, ADR rebaseline, archive/deprecation plan, and current-system rewrite

## Intent

DOC-001 is not a sentimental documentation cleanup. It is a rebaseline campaign.

The goal is to make the project understandable again by reducing the active
documentation surface and rebuilding the current architecture narrative from the
actual system state.

## Core principle

When documentation drift is severe, prefer this order:

1. identify the current truth,
2. archive or deprecate obsolete artifacts,
3. rewrite a smaller coherent documentation set,
4. avoid patching outdated narratives into a confusing hybrid.

Old documents may remain historically useful, but they must not masquerade as
current architecture truth.

## Documentation layers

### Current Truth

A small set of documents that describe the current system:

- repository entry point and purpose,
- current architecture and system overview,
- pipeline state machine,
- agent governance and responsibility model,
- current operational runbook,
- current diagrams and system representations.

### Reference

Technical detail that remains useful but is not the main narrative:

- database tables,
- data-source capabilities,
- connector contracts,
- security/design guidance,
- glossary.

### Historical / Archive

Build logs, planning notes, source-analysis experiments, old candidate reviews,
and historical decision context.

These are useful for traceability, but they are not current architecture truth
unless explicitly promoted.

### Runtime exports

`exports/` contains runtime reports and generated review artifacts. These can be
useful evidence, but they are not maintained documentation and must not be used as
pipeline input or as the primary current-system narrative.

## ADR rebaseline

DOC-001 must include an ADR rebaseline check:

- Current
- Superseded
- Historical
- Needs rewrite

The project should not create many new ADRs just to backfill every detail.
New ADRs should be reserved for stable system-wide decisions such as agent
governance, documentation rebaseline policy, stop reassessment strategy, or
architecture-boundary changes.

## Planning docs

`docs/planning/` should be treated as historical build logs by default.

A planning document may become Current Truth only if DOC-001 explicitly promotes
its content into a current architecture, governance, or operator document.

## Source-analysis docs

`docs/source_analysis/` should be treated as historical or reference material by
default. Some content may be valuable, but the directory should not be the primary
place a reader learns the current system.

## Required DOC-001 outputs

DOC-001 should produce:

- a documentation inventory report,
- an ADR rebaseline report,
- a reduced Current Truth documentation map,
- an archive/deprecation plan,
- current architecture/system diagrams,
- a README/runbook reconciliation plan.

## Non-goals

DOC-001 should not:

- rewrite every document,
- preserve every old artifact in the active reader path,
- turn historical planning notes into architecture truth,
- add new pipeline logic,
- change database or runtime behavior.
