# ADR-034: Define Shared JAP Product and Runtime Coexistence

Status: Accepted
Date: 2026-09-16

## Context

JAP now has two intentionally different runtime paths:

- the established local/offline product in `job-application-pipeline`, including local PostgreSQL, WSL/private runtime state and the React Control Center presented locally through the Windows WebView2 shell;
- `jap-cloud-based`, which is building an Azure-hosted runtime with Azure PostgreSQL, FastAPI, Container Apps, managed identity and cloud lifecycle controls.

These runtimes must not evolve into two independent products. The cloud path exists to transport the same JAP product into a different runtime and infrastructure environment, not to create competing ranking, gate, Top-5, application or data-layer semantics.

At the same time, there is no need for a big-bang migration. The local product is useful, proven and a strong offline fallback. The cloud runtime can mature beside it until it has enough parity and operational evidence to become the primary runtime by explicit operator choice.

## Decision

JAP is one product with multiple runtime and presentation transports.

`job-application-pipeline` remains the current upstream authority for JAP product semantics. `jap-cloud-based` owns bounded cloud adaptation, Azure infrastructure, cloud-specific adapters, migration, release and lifecycle evidence.

The following invariants apply:

1. **One product truth.** Ranking, hard filters, gates, Top-5 semantics, domain identifiers, application rules, Bronze/Silver/Gold meanings and operator-facing product contracts must not be independently reimplemented with different semantics in the cloud repository.
2. **Runtime-specific adapters are expected.** Local WSL/files/PostgreSQL/WebView2 concerns and Azure PostgreSQL/FastAPI/Container Apps/Managed Identity/ACR concerns may differ because they are infrastructure and transport boundaries, not separate product definitions.
3. **The React Control Center is a portable product surface.** WebView2 is a local presentation shell, not the product UI authority. The same Control Center may be hosted in a browser/Azure runtime against a compatible product API.
4. **Streamlit is supplemental presentation.** It may remain a cloud/demo/analytics surface, but it does not become an independent source of JAP product truth.
5. **Shared code moves toward versioned reuse.** Product/domain logic and stable API/DTO contracts should converge into reusable, source-bound modules or artifacts owned upstream rather than being copied into the cloud repository. A third repository is not required to begin this separation.
6. **Cloud provenance is explicit.** A cloud release that consumes JAP product behavior or data must bind the exact upstream source SHA and, once introduced, the exact shared-core/contract artifact version.
7. **Parallel operation is intentional.** Local/offline JAP remains a first-class fallback while JAP Cloud matures. Parallel runtimes are not architectural drift when both implement the same product contracts.
8. **Cloud succession is evidence-driven, not date-driven.** JAP Cloud may later replace the local runtime as the primary operator path, but only after explicit parity evidence and an explicit operator decision.

## Runtime model

```text
                    JAP product semantics
         ranking / gates / DTOs / domain / data layers
                             |
                    stable product ports
                 /-----------+-----------\
                /                        \
        local runtime                 cloud runtime
   WSL + local PostgreSQL       Azure PostgreSQL + FastAPI
   local/private adapters       Azure/cloud adapters
                \                        /
                 \----------+-----------/
                            |
                  React Control Center
                  /                  \
          WebView2/local          browser/Azure

        Streamlit remains an additional cloud surface.
```

## Demo and transition model

The preferred demonstration order is:

1. **JAP Cloud** as the primary cloud-native demo;
2. **JAP Classic Web on Azure** as a bounded compatibility/fallback surface using the canonical React Control Center, a read-only compatibility API and a clearly identified sanitized/checksummed JAP-derived demo snapshot;
3. **JAP Offline** through the existing Windows/WebView2 + WSL runtime as the independent offline fallback.

The Classic Web fallback must never present a fixture or snapshot as live operational truth and must not create a second mutation authority. Its role is presentation continuity while the cloud runtime reaches product parity.

## Cloud succession criteria

A later decision may make JAP Cloud the primary or sole normal operator runtime only when evidence covers at least:

- product-contract parity for the operator-critical workflows;
- compatible API/DTO behavior for the shared product surface;
- proven migration integrity and provenance for required JAP data/state;
- release, runtime identity, rollback and recovery evidence;
- acceptable lifecycle and FinOps behavior;
- an acceptable contingency/offline posture;
- explicit operator acceptance of the transition.

Meeting some of these criteria does not silently retire the local runtime.

## Consequences

- Cloud work should prefer adapters and transport changes over copied business logic.
- The existing React Control Center becomes a strategic bridge between local and cloud runtimes.
- The current local Windows application remains valid; its WebView2 shell is one presentation transport for the shared UI.
- JAP Cloud can evolve quickly without forcing risky synchronization or premature decommissioning of local JAP.
- Product changes made upstream should have a deliberate compatibility/version path into the cloud runtime.

## Prohibited drift

The following patterns require an explicit architecture replan rather than silent adoption:

- copying ranking/gate/application business logic into JAP Cloud and allowing it to diverge;
- creating independent cloud-only product semantics for the same operator concept;
- treating a demo snapshot as a second source of truth;
- forking the React Control Center without a deliberate compatibility contract;
- declaring the local product retired because a cloud demo exists.

## Non-goals

This ADR does not change the active JAP Cloud M2 acceptance scope, authorize Azure effects, move private local documents to Azure, or require immediate extraction of a shared package. It defines the long-lived architecture boundary within which those later migrations can happen incrementally.

## Counterpart

The mirrored cloud-side decision is JAP Cloud ADR-0003: https://github.com/jenshaberle-dotcom/jap-cloud-based/blob/main/docs/decisions/ADR-0003-shared-jap-product-runtime-coexistence.md
