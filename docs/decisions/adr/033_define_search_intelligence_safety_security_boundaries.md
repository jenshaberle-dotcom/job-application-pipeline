# ADR-033: Define Safety and Security Boundaries for Search Intelligence Agents

Status: Accepted
Date: 2026-06-07

## Context

The project has evolved from ingestion scripts into a Search Intelligence system with market sensors, candidate promotion, URL discovery, evidence gates, connector artifact generation, scheduler ideas and a Control Center.

Recent EO-002B to EO-002D work showed that the system can now diagnose URL-Finder behavior and repair specific false-negative paths. It also showed that further automation would create risk without explicit safety, security and state contracts.

## Decision

The project adopts ARCH-001 as an active architecture baseline.

The following contracts are now required for future work:

- safety zones for read-only, write, activation, scheduler and destructive actions
- agent permission boundaries
- pipeline state machine for candidate lifecycle transitions
- gate contracts with diagnosis fields
- security baseline for external requests, secrets and report hygiene
- architecture freeze rule for 90+ maturity campaign

## Consequences

Future feature work must identify its safety zone, affected agent permissions, allowed state transitions and gate contract impact.

New ideas do not change the active architecture unless the expected improvement is roughly 15 to 20 points in a named maturity area or closes a measured pipeline gap.

Scheduler, source activation, destructive cleanup and active_controlled changes remain gated.

## Non-goals

This ADR does not implement all technical enforcement. It creates the contract that later enforcement must follow.

## Follow-up

High-priority follow-ups:

- EO-002E Gate Stop / Next-Safe-Action Evidence Analysis
- EO-002F URL Finder Runtime Hardening
- security enforcement for blocked network targets and total runtime budgets
