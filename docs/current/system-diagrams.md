# Current System Diagrams

Status: current truth  
Active product track: **PRODUCT-RECOVERY-001 / issue #783**  
Release checkpoint: `v0.1.0-demo.1`

## Purpose

These diagrams show the current product architecture after DEMO-001 salvage. They deliberately distinguish discovery provenance, Employer-Origin authority, currentness, Product V1 ranking and application preparation while preserving the bounded Search Intelligence discovery and repair loops that feed the product path.

## End-to-end Search Intelligence control surface

The bounded acquisition/control layer remains upstream of Product V1. `Promotion Gatekeeper` controls which discoveries may advance; `Origin URL Detective` resolves bounded source evidence before Employer-Origin/current-vacancy authority is claimed.

```mermaid
flowchart LR
    S0[Market Sensors / Aggregators]
    S1[Discovery Evidence]
    S2[Promotion Gatekeeper]
    S3[Origin URL Detective]
    S4[Employer-Origin Resolution]
    S5[Exact Vacancy Verification]
    S6[Bronze / Silver]
    S7[Product V1 Gates]
    S8[Control Center]
    S9[Application Workspace]

    S0 --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9
    S2 -.blocked / uncertain.-> R0[Review / repair]
    S3 -.no supported origin.-> R0
    R0 -.bounded retry with new evidence.-> S2
```

## Learning and repair loops

Search Intelligence remains evidence-driven rather than fail-open. Suspected false negatives, source gaps, rejected origin patterns and stale/detail-drift findings feed bounded learning or repair; they do not silently grant Product authority.

```mermaid
flowchart TB
    OBS[Observability / Control Center]
    MISS[False-negative pressure]
    DISC[Discovery / search-term learning]
    PROMO[Promotion Gatekeeper]
    URL[Origin URL Detective]
    DETAIL[Employer-Origin detail evidence]
    STOP[Stopper / stale-state reassessment]
    GATE[Evidence and Product gates]

    OBS --> MISS --> DISC --> PROMO --> URL --> DETAIL --> GATE --> OBS
    DETAIL --> STOP
    GATE --> STOP
    STOP -->|bounded repair evidence| PROMO
    STOP -->|hard stop| OBS
```

## 1. End-to-end product-value flow

```mermaid
flowchart LR
    S0[Market Sensors / Aggregators<br/>BA, StepStone, source feeds]
    S1[Discovery Evidence<br/>employer + job observations]
    S2[Employer-Origin Resolution<br/>career/ATS/source authority]
    S3[Exact Vacancy Verification<br/>current detail + fingerprint]
    S4[Bronze<br/>raw observation + lineage]
    S5[Silver<br/>canonical job]
    S6[Assessment<br/>current vacancy-bound evidence]
    S7[Capability Fit + Hard Filters]
    S8[Deterministic Ranking<br/>rankable]
    S9[Top-5 Policy<br/>score >= 70, max 5]
    S10[Control Center<br/>review + evidence]
    S11[Application Workspace]
    S12[CV + Letter<br/>DOCX / PDF / ZIP<br/>draft_for_review]

    S0 --> S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9 --> S10 --> S11 --> S12

    S1 -.aggregator-only / unresolved.-> D0[Discovery-only lane]
    S3 -.closed / stale / unverifiable.-> H0[Historical / blocked]
    S7 -.fail / required unknown.-> R0[Review / evidence required]
    S8 -.below 70.-> R1[Rankable but not recommended]
```

## 2. Discovery truth vs Product action truth

```mermaid
flowchart TB
    A[Aggregator discovery<br/>BA / StepStone / GuteJobs]
    P[Discovery provenance<br/>source_name + historical source_url]
    O[Resolved Employer-Origin<br/>verified vacancy URL]
    C[Currentness proof<br/>exact detail + closure/fingerprint]
    X[Product action URL]
    T[Top-5 / Application authority]

    A --> P
    P --> O
    O --> C
    C --> X
    X --> T

    P -.not sufficient.-> N[Discovery-only]
```

Core invariant:

```text
where a job was discovered != where Product/Application action authority comes from
```

## 3. Currentness and detail-drift loop

```mermaid
flowchart LR
    DB[Stored assessment<br/>detail fingerprint]
    LIVE[Live Employer-Origin detail]
    CMP{Fingerprint / activity match?}
    KEEP[Assessment remains current]
    REFRESH[Audited assessment refresh]
    RESET[Invalidate stale downstream evidence]
    GATES[Capability -> Hard Filter -> Ranking]
    CLOSED[Not current/actionable]

    DB --> CMP
    LIVE --> CMP
    CMP -->|same + active| KEEP --> GATES
    CMP -->|content drift| REFRESH --> RESET --> GATES
    CMP -->|closed/dead| CLOSED
```

## 4. Rankable vs recommended

```mermaid
flowchart LR
    A[Current Employer-Origin job]
    B[Assessment current]
    C[Capability fit resolved]
    D[Hard filters passed]
    E[4 ranking components present]
    F[Rankable]
    G{Overall score >= 70?}
    H[Top-5 candidate]
    I[Rankable only<br/>not recommended]

    A --> B --> C --> D --> E --> F --> G
    G -->|yes| H
    G -->|no| I
```

`PD-050/PD-051` remain product authority: Top 5 is at most five and is not filled with below-threshold jobs.

## 5. Application preparation authority

```mermaid
flowchart TB
    U[Explicit operator Generate]
    CV[Approved base CV]
    LT[Approved base letter]
    CF[Candidate Facts<br/>candidate factual authority]
    JV[Exact current vacancy evidence<br/>job factual authority]
    LLM[Provider structured drafting]
    FB[Evidence-first fallback]
    VAL[Grounding / package validation]
    EXP[Local renderer]
    OUT[CV.docx + CV.pdf<br/>Letter.docx + Letter.pdf<br/>ZIP]
    REVIEW[draft_for_review]
    NOAUTO[No submit / no send]

    U --> CV
    U --> LT
    U --> CF
    U --> JV
    CV --> LLM
    LT --> LLM
    CF --> LLM
    JV --> LLM
    LLM --> VAL
    LLM -.provider/validation failure.-> FB --> VAL
    VAL --> EXP --> OUT --> REVIEW --> NOAUTO
```

## 6. Data layers and observability

```mermaid
flowchart TB
    RAW[Bronze<br/>observations + lineage]
    SILVER[Silver<br/>canonical jobs]
    GOLD[Gold / Product V1<br/>assessment + read models]
    METRICS[Data Layers<br/>inventory / flow / coverage / freshness]
    UI[React Control Center]

    RAW --> SILVER --> GOLD --> UI
    RAW --> METRICS
    SILVER --> METRICS
    GOLD --> METRICS

    METRICS -.observes only.-> UI
```

Data-layer metrics are observability. They do not create ranking, source activation or application authority.

## 7. Employer/source acquisition lifecycle

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

## 8. Product Recovery architecture target

```mermaid
flowchart LR
    NOW[Current state<br/>many capable components<br/>multiple repair helpers]
    T1[Truth propagation<br/>origin + freshness end-to-end]
    T2[Single normal orchestrator]
    T3[Rankable throughput]
    T4[>=5 recommendations<br/>meeting approved threshold]
    T5[Near-submission application quality]
    T6[Complexity harvest<br/>release checkpoint]

    NOW --> T1 --> T2 --> T3 --> T4 --> T5 --> T6
```

The target is not another demo-only coordinator. The target is one normal observable product path that produces the same truthful outcome from cold state.

## 9. Release and proof model

```mermaid
flowchart LR
    PR[PR / implementation]
    CI[Pipeline CI]
    RE[Re-entry identity]
    MAIN[Canonical main]
    RR[Versioned Release Request]
    RM[Release Management]
    REL[GitHub Release<br/>features + bug fixes + limitations]
    OP[Local operator proof<br/>runtime-only facts]

    PR --> CI --> MAIN
    PR --> RE --> MAIN
    MAIN --> RR --> RM --> REL
    OP -.separately labeled evidence.-> REL
```

CI is not a substitute for live PostgreSQL/provider/employer-HTTP evidence. Local operator proof is not portable repository state.

## Diagram maintenance rule

Update this file when:

- an authority boundary changes;
- the normal cold-to-application path changes;
- a Product V1 stage or hard gate changes responsibility;
- application-generation authority changes;
- release/proof behavior changes materially;
- PRODUCT-RECOVERY-001 retires or consolidates a major recovery path.

Do not update it for every helper script or historical repair experiment.
