# Current System Diagrams

Status: current truth
Scope: DOC-001G architecture diagram rebaseline
Last rebaseline: DOC-001G

## Purpose

This document is the current diagram entry point for the project.

The diagrams follow the Deep Ocean / Search Intelligence design language, but
they stay GitHub-friendly and maintainable. Mermaid diagrams are preferred
because architecture visuals must be reviewable, versioned and easy to update.

Older diagrams may still be useful historically, but this file represents the
current architecture story after DOC-001G.

## End-to-end Search Intelligence control surface

```mermaid
flowchart LR
    S0[Market Sensors<br/>BA, StepStone, ATS, employer signals]
    S1[Signal Basin<br/>raw observations and market evidence]
    S2[Candidate Discovery<br/>company and source candidates]
    S3[Promotion Gatekeeper<br/>Türsteher / candidate promotion]
    S4[Origin URL Detective<br/>bounded source URL discovery]
    S5[Detail Evidence Discovery<br/>concrete job/detail evidence]
    S6[Evidence Gates<br/>diagnosis, confidence, next safe action]
    S7[Connector Candidate Chain<br/>build readiness and validation]
    S8[Active Controlled Source<br/>approved source operation]
    S9[Bronze / Silver / Gold<br/>raw, canonical, decision models]
    S10[Control Center<br/>operator state, blockers, alerts]

    S0 --> S1 --> S2 --> S3 --> S4 --> S5 --> S6
    S6 -->|supported| S7 --> S8 --> S9 --> S10
    S6 -->|blocked / uncertain| R0[Stopper Reassessment]
    R0 -->|stage-2 dry-run repair plan| S4
    R0 -->|hard stop or unclear| H0[Manual Review]
    S10 -.learning signals.-> S0
    S10 -.candidate feedback.-> S3
    S10 -.evidence feedback.-> S5
```

## Candidate and connector lifecycle

```mermaid
stateDiagram-v2
    [*] --> discovered
    discovered --> promotion_recommended
    discovered --> rejected_or_parked
    promotion_recommended --> origin_url_required
    promotion_recommended --> manual_review_required
    origin_url_required --> origin_url_candidate_found
    origin_url_candidate_found --> origin_url_validated
    origin_url_candidate_found --> manual_review_required
    origin_url_validated --> detail_evidence_required
    detail_evidence_required --> detail_evidence_found
    detail_evidence_required --> manual_review_required
    detail_evidence_found --> connector_candidate
    detail_evidence_found --> stopper_reassessment
    stopper_reassessment --> detail_evidence_required: repair plan / dry-run
    stopper_reassessment --> manual_review_required
    connector_candidate --> build_approval_required
    build_approval_required --> connector_artifact_generated
    connector_artifact_generated --> validation_required
    validation_required --> approval_required
    approval_required --> active_controlled
    approval_required --> manual_review_required
    active_controlled --> monitor
    active_controlled --> deactivation_review_required
    manual_review_required --> rejected_or_parked
```

## Learning and repair loops

```mermaid
flowchart TB
    OBS[Observability and Control Center]
    MISS[False-negative pressure<br/>missed or suspected missed employers]
    TERM[Search-term learning<br/>yield, noise, coverage gaps]
    COMP[Company discovery cycle<br/>known-company suppression and rotation]
    URL[Origin URL learning<br/>hosts, providers, rejected patterns]
    DETAIL[Detail evidence learning<br/>sample jobs, mismatch reasons]
    STOP[Stopper reassessment<br/>valid, stale, over-sensitive stops]
    GATE[Gate calibration<br/>diagnosis quality and next safe action]

    OBS --> MISS
    MISS --> TERM
    MISS --> COMP
    TERM --> COMP
    COMP --> URL
    URL --> DETAIL
    DETAIL --> GATE
    GATE --> STOP
    STOP -->|repair plan| URL
    STOP -->|hard stop evidence| OBS
    GATE --> OBS
```

## Agent responsibility boundaries

```mermaid
flowchart TB
    Q[Queue / Next Safe Action Agent]
    S[Stopper Reassessment Agent]
    R[Repair Agents]
    G[Gate Agents]
    A[Approval / Lifecycle Agents]
    C[Connector / Source State]
    GOV[GOV-001 Governance]

    Q -->|routes only| S
    Q -->|routes only| R
    Q -->|routes only| G
    S -->|audits stop validity| P[Stage-2 Repair Plan]
    P -->|explicit operator execution only| R
    R -->|produces evidence or repair output| G
    G -->|evaluates evidence| A
    A -->|controlled transition| C

    GOV -.classifies.-> Q
    GOV -.classifies.-> S
    GOV -.classifies.-> R
    GOV -.classifies.-> G
    GOV -.classifies.-> A
```

## Data and decision layers

```mermaid
flowchart TB
    RAW[Bronze<br/>tolerant raw acquisition]
    SILVER[Silver<br/>canonical jobs]
    GOLD[Gold<br/>decision and observability read models]
    UI[Control Center<br/>product surface]

    CAND[Employer-Origin Candidates]
    EVID[Evidence and Gate Events]
    STOP[Stopper Reassessment Events]
    SRC[Source Value and Lifecycle]

    RAW --> SILVER --> GOLD --> UI
    CAND --> EVID --> GOLD
    EVID --> STOP --> EVID
    SRC --> GOLD
    UI -.operator action / review.-> CAND
```

## Documentation rebaseline model

```mermaid
flowchart LR
    INV[DOC-001A Inventory]
    MAP[DOC-001B/C Current Truth Map]
    STATUS[DOC-001G Architecture Status]
    CUR[Current Truth Docs]
    REF[Reference Docs]
    ARC[Historical / Archive Docs]
    ADR[ADR Rebaseline]

    INV --> MAP --> STATUS
    STATUS --> CUR
    STATUS --> REF
    STATUS --> ARC
    STATUS --> ADR

    CUR --> README[README]
    CUR --> ARCH[Current System Overview]
    CUR --> DIAG[System Diagrams]
    CUR --> GOV[Governance]
    CUR --> RUN[Operator Runbook]
```

## Diagram maintenance rule

This file should be updated when:

- a new product-agent responsibility is introduced,
- a pipeline stage changes responsibility,
- a new gate/stage changes candidate progression,
- a new learning or repair loop becomes part of the intended architecture,
- the Current Truth documentation map changes,
- DOC-001 archives or promotes a major documentation area.

It should not be updated for every small helper script, planning note, or runtime
report.
