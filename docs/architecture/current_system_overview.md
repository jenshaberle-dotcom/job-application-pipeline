# Current System Overview

Status: current truth candidate  
Scope: DOC-001B architecture rebaseline  
Last rebaseline: DOC-001B

## Product intent

The project is a personal job-market intelligence pipeline for the Hannover and
remote-in-Germany market.

It is no longer just a job scraper demo. The current system is a controlled
Search Intelligence product that combines:

- defensive source ingestion,
- source and candidate discovery,
- evidence collection,
- gate-based progression,
- connector candidacy,
- controlled activation,
- observability,
- governance and documentation guards.

The system is optimized for reducing false negatives without turning broad,
untrusted discovery signals into uncontrolled source activation.

## Current architecture in one sentence

Market and source signals flow through controlled discovery, evidence, gate,
repair, and connector-readiness stages before anything can become an active
controlled source.

```text
Market Sensors
  -> Candidate / Source Discovery
  -> URL / Origin / Detail Evidence
  -> Gates and Stopper Reassessment
  -> Connector Candidate / Build / Validation / Approval
  -> Active Controlled Source
  -> Bronze / Silver / Gold / Control Center
```

## Core pipeline stages

### 1. Market and source sensors

Sensors and aggregators are used to discover potential employers, market
coverage gaps, and search-space signals.

Important boundary:

- aggregators are discovery inputs, not automatically trusted source truth,
- employer-origin sources may be valuable even with low volume if they add unique
  relevant jobs,
- new sensor expansion is frozen unless it materially improves safety, diagnosis,
  generics, or maturity.

### 2. Candidate and source discovery

Candidate discovery turns market signals into employer-origin candidates.

The current system tracks candidate identity, source-family candidates,
source-name candidates, candidate URLs, risk levels, and lifecycle/gate status.

Important boundary:

- missing URLs remain missing/NULL, not fake placeholder values,
- candidate identity errors are safety issues,
- source URL discovery and candidate promotion must stay bounded and auditable.

### 3. Origin URL and detail evidence

Origin URL discovery and detail evidence discovery try to find concrete career
source URLs and job detail pages.

The current detail evidence layer has been tightened:

- candidate hosts are prioritized,
- rejected/audit URLs do not feed back into the seed path,
- preliminary candidates are separated from supported detail evidence,
- foreign-domain and employer mismatch risks are stricter,
- location signals such as "Hannover" inside an employer name are not enough.

### 4. Gates, stops, and stopper reassessment

Gates decide whether evidence is sufficient to progress.

Stops are not automatically accepted as final truth. STOP-001 introduced a
dedicated stopper reassessment path:

```text
Stop signal
  -> Stop validity audit
  -> False-negative risk assessment
  -> Stage-2 dry-run/apply repair plan
```

Important boundary:

- the stopper reassessment agent does not unblock candidates automatically,
- Stage-2 commands are planned only unless explicitly executed,
- safety/legal/access stops may remain hard stops.

### 5. Connector candidacy and build chain

Connector candidacy starts only after adequate evidence and gate progression.

Connector-related agents and plans must distinguish:

- connector candidacy,
- artifact generation,
- validation,
- registration planning,
- final approval,
- active controlled operation.

Important boundary:

- connector artifacts are not source activation,
- source activation requires explicit approval/gate progression,
- repair agents do not approve their own results.

### 6. Active controlled sources and job layers

Only active controlled sources may contribute operationally through the job
pipeline.

The job-data layers remain conceptually:

- Bronze: tolerant/raw-first acquisition and preservation,
- Silver: canonical job representation and quality filtering,
- Gold: decision/observability/control-center read models.

Important boundary:

- CSV/Excel/local exports are human-readable outputs only,
- export artifacts must never become hidden pipeline inputs or activation gates.

### 7. Control Center and observability

The Control Center is the product surface for Search Intelligence state.

It should show:

- source landscape,
- candidate lifecycle,
- gate status,
- next safe actions,
- blocker and false-negative pressure,
- agent/health summaries,
- activity and alerts.

The current Agent Monitor and governance work distinguish derived status from
true runtime health. Future work should improve agent-level observability.

## Current governance state

GOV-001 introduced the current governance frame:

- agent registry foundation,
- agent classification catalog,
- agent responsibility model,
- agent capability audit matrix,
- governance/documentation drift guard.

New agent-like scripts must not appear without governance classification and
capability-audit consideration.

## Current documentation state

DOC-001 is the documentation rebaseline campaign.

Current principle:

- keep a small Current Truth layer,
- keep technical reference docs where useful,
- treat planning and source-analysis docs as historical by default,
- rebaseline ADRs explicitly,
- archive/deprecate misleading artifacts rather than patching obsolete narratives.

## Architecture boundaries

The system should keep these boundaries:

| Boundary | Rule |
|---|---|
| Sensor vs source | Discovery signal is not active source truth. |
| Candidate vs connector | Candidate evidence does not imply connector registration. |
| Repair vs approval | Repair agents do not approve their own results. |
| Queue vs repair | Queue agents route; they do not repair. |
| Gate vs discovery | Gates evaluate evidence; they do not discover evidence. |
| Stop vs false negative | Stops are audit inputs, not unquestioned final truth. |
| Report vs input | Exports are reports, never pipeline inputs. |
| Current docs vs history | Historical notes must not look like current architecture. |

## Current highest documentation priorities

1. Rebuild the architecture and system diagrams from the actual current system.
2. Rebaseline ADRs.
3. Reduce active documentation entry points.
4. Archive/deprecate planning and source-analysis sprawl.
5. Keep GOV-001 guardrails active during all future changes.
