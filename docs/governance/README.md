# Governance

This directory contains the lightweight operating governance for the Job Application Pipeline.

The goal is not to create a heavyweight project-management system. The goal is to keep a fast-moving, AI-assisted engineering project honest, reviewable and production-oriented.

## Documents

- [Governance Foundation](governance_foundation.md) defines the required review checks and decision boundaries.
- [Documentation Drift Baseline](documentation_drift_baseline.md) captures the current documentation gap and the correction strategy.

## Current Rule

Governance must be small enough to use before every meaningful implementation block, but explicit enough to stop hidden drift.

If implementation, documentation and chat context disagree, the repository must be reconciled before the next large mutation of system behavior.

## Current Next Block

The next development block is expected to be:

**EO-002B Candidate Reprocessing & URL Finder Validation**

That block should start only after the DOC-001/DOC-002 baseline is merged or consciously accepted as the active working baseline.

<!-- ARCH-001-SAFETY-SECURITY-STATE:START -->
## Architecture Freeze Governance

Architecture freeze is now an active governance rule.

During maturity mode, a new idea enters active scope only when it is expected to improve a named maturity area by roughly 15 to 20 points or close a measured pipeline gap. Otherwise it is parked in the White-Whale or product backlog.

ARCH-001 is the governing baseline for safety zones, security boundaries, agent permissions, lifecycle transitions and gate contracts.
<!-- ARCH-001-SAFETY-SECURITY-STATE:END -->
