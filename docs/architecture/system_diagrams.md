# Current System Diagrams

Status: current truth candidate  
Scope: DOC-001B diagram rebaseline  
Last rebaseline: DOC-001B

## Purpose

This document contains the current high-level system diagrams for the project.

Older diagrams may still be useful historically, but this file is intended to
be the current diagram entry point after DOC-001.

## Search Intelligence pipeline

```mermaid
flowchart LR
    A[Market Sensors<br/>BA, StepStone, existing sources] --> B[Candidate Discovery]
    B --> C[Origin URL Discovery]
    C --> D[Detail Evidence Discovery]
    D --> E[Gate Evaluation]
    E -->|passed| F[Connector Candidate Chain]
    E -->|blocked or uncertain| G[Stopper Reassessment]
    G -->|stage-2 dry-run plan| D
    G -->|hard stop| H[Manual Review / Stop]
    F --> I[Connector Build / Validation]
    I --> J[Final Approval]
    J --> K[Active Controlled Source]
    K --> L[Bronze / Silver / Gold]
    L --> M[Control Center / Observability]
```

## Candidate lifecycle view

```mermaid
stateDiagram-v2
    [*] --> discovery
    discovery --> source_url_review_required
    discovery --> detail_evidence_required
    source_url_review_required --> origin_url_recovery
    origin_url_recovery --> detail_evidence_required
    detail_evidence_required --> detail_evidence_gate
    detail_evidence_gate --> connector_candidate: evidence supported
    detail_evidence_gate --> stopper_reassessment: blocked or suspicious stop
    stopper_reassessment --> detail_evidence_required: repair plan / dry-run
    stopper_reassessment --> manual_review_required: uncertain or hard stop
    connector_candidate --> build_approval_required
    build_approval_required --> connector_validation
    connector_validation --> final_approval_gate
    final_approval_gate --> active_controlled
    final_approval_gate --> manual_review_required
    active_controlled --> source_lifecycle_tracking
```

## Governance and responsibility boundaries

```mermaid
flowchart TB
    Q[Queue / Next Safe Action] -->|routes| S[Stopper Reassessment]
    Q -->|routes| R[Repair Agents]
    Q -->|routes| G[Gate Agents]

    S -->|audits stop validity| P[Stage-2 Repair Plan]
    P -->|explicit operator execution only| R

    R -->|produces evidence / repair output| G
    G -->|evaluates evidence| A[Approval / Lifecycle Agents]
    A -->|controlled transition| C[Connector / Source State]

    GOV[GOV-001 Governance] -.classifies.-> Q
    GOV -.classifies.-> S
    GOV -.classifies.-> R
    GOV -.classifies.-> G
    GOV -.classifies.-> A
```

## Documentation rebaseline model

```mermaid
flowchart LR
    INV[DOC-001A Inventory] --> MAP[DOC-001B Current Truth Map]
    MAP --> CUR[Current Truth Docs]
    MAP --> REF[Reference Docs]
    MAP --> ARC[Historical / Archive Docs]
    MAP --> ADR[ADR Rebaseline]

    CUR --> README[README]
    CUR --> ARCH[Current System Overview]
    CUR --> DIAG[System Diagrams]
    CUR --> GOV[Governance]
    CUR --> RUN[Operator Runbook]

    ARC --> PLAN[docs/planning]
    ARC --> SRC[docs/source_analysis]
    ARC --> STATE[docs/project_state]
```

## Data and decision layers

```mermaid
flowchart TB
    RAW[Raw / Bronze<br/>tolerant acquisition] --> SILVER[Silver<br/>canonical jobs]
    SILVER --> GOLD[Gold<br/>decision read models]
    GOLD --> UI[Control Center]

    CAND[Employer-Origin Candidates] --> GATES[Gate Reviews / Events]
    GATES --> GOLD
    GATES --> STOP[Stopper Reassessment]
    STOP --> GATES

    SRC[Source Value / Lifecycle] --> GOLD
```

## Diagram maintenance rule

This file should be updated when:

- a new product-agent responsibility is introduced,
- a pipeline stage changes responsibility,
- a new gate/stage changes candidate progression,
- the Current Truth documentation map changes,
- DOC-001 archives or promotes a major documentation area.

It should not be updated for every small helper script, planning note, or runtime
report.
