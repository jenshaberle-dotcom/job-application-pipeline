# ADR-038: Reconcile portal evidence and reusable factory sources

Status: Proposed
Date: 2026-11-07

## Context

Operator packages accumulated reviewed URL/ATS rules outside Git history, while
a remote TECH PoC independently connected public directories to the existing
factory. A clean WSL checkout did not prove those maintenance changes were backed
up. Registers, portal candidates, job samples and production admission also have
different evidence strengths.

## Decision

Maintain reusable JAP discovery/parsing rules in the JAP repository, importing
the existing compiler instead of copying it. Combine registry candidates and
observed sensor/Census/navigation metadata, with independent publisher and exact
ATS-tenant verification. Ambiguous aliases require reconciliation; a directory
match or model output never grants ownership or runtime admission.

Keep first-discovery and assisted provenance separate. Keep concrete job proof,
profile relevance and production approval separate. Preserve the frozen mixed
TECH/SOCIAL evaluation population and report unattempted records and long-tail
classes. Retain the TECH PoC as an experiment; do not silently use it as Christina's
production profile or daily scheduler.

Publish reviewed source, tests and architecture against exact Git parents with
remote readback. Raw payloads, secrets and private documents need a separate
private backup. This source integration neither deploys nor changes the GUI.

## Consequences and alternatives

The package-to-repository mapping and offline replay become auditable. XML_FEED
is a supported candidate strategy label, not automatic production enablement.
Blind branch replacement and copying whole operator directories were rejected.
The branch's separate orphan-backup workflow is deferred because it targets
Classic/Runtime rather than the exact JAP/RCC integration requested here.

## Verification

See [integration review](../../current/URLFINDER-SOURCE-INTEGRATION.md) and
[arc42 supplement](../../current/urlfinder-factory-arc42.md). Tests and retained
field evidence do not constitute the user's 90% or daily-delivery acceptance.
