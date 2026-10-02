# Current System Architecture

Status: current truth
Scope: product-level architecture after DOC-001M

## Architecture in one sentence

Market signals remain weak evidence until bounded discovery, origin/detail checks,
explicit gates and controlled approval make them operational input.

```text
Market Sensors
  -> Candidate / Source Discovery
  -> URL / Origin / Detail Evidence
  -> Gates and Stopper Reassessment
  -> Connector Candidate / Build / Validation / Approval
  -> Active Controlled Source
  -> Recurring Monitoring Admission
  -> Deterministic Due-Work Schedule
  -> Connector Execution
  -> Bronze / Silver / Gold / Control Center
  -> Fleet Health + Yield
  -> next due execution
```

## Core boundaries

| Boundary | Rule |
|---|---|
| Sensor vs source | Discovery signal is not active source truth. |
| Candidate vs connector | Candidate evidence does not imply connector registration. |
| Evidence vs approval | Repair agents can produce evidence; they do not approve themselves. |
| Queue vs repair | Queue agents route; they do not repair. |
| Gate vs discovery | Gates evaluate evidence; they do not discover it. |
| Stop vs false negative | A stop is an audit input, not automatically final truth. |
| Report vs input | Exports are reports, never hidden pipeline inputs. |
| Current docs vs history | Historical notes must not look like current architecture. |

## Main system areas

### Market sensors

Market sensors and aggregators discover companies, source targets and search spaces.
They are bounded discovery inputs, not canonical source truth.

### Candidate and origin discovery

Candidate discovery turns signals into employer-origin candidates. Missing URLs stay
missing, and ambiguous candidates must not be treated as validated.

### Detail evidence and gates

Origin/detail evidence precedes connector work. Gates decide progression; stops carry
a reason, next safe action and manual-review path.

### Connector path

Connector candidacy, build, validation, registration, approval and controlled operation
are separate stages; artifacts are not activation.

Accepted Employer-Origin candidates require an explicit connector disposition:
runnable definition, evidence-backed block/review, or evidence-backed rejection.
Active-controlled sources are incomplete until recurring monitoring is dispositioned.
`config/connector_fleet_policy.json` owns cadence, deterministic staggering, bounded
concurrency and GREEN/YELLOW/RED semantics. Technical health and recent relevant-job
yield stay separate; zero yield alone is not a technical failure.

See `../decisions/adr/037_close_connector_fleet_lifecycle.md`.

### Job data layers

- Bronze keeps bounded raw acquisition and lineage.
- Silver builds canonical job representation and quality filtering.
- Gold provides decision, observability and Control Center read models.

### Application generation

F6 has one automatic CV/letter authority: `gpt-6.1-sol` through the
ChatGPT-authenticated bundled Codex runtime. Its fixed profile is evidence `medium`,
strategy/CV/letter `high`, adversarial critic `xhigh`, and final rewrite `high`.
Approved Candidate Facts are mandatory provenance. At most two `high` layout-only
compaction passes may follow; they never replay the six semantic stages.
No model/reasoning override, API-key generator or automatic prose fallback exists.
`local_private` is an explicit manual no-LLM mode, not a second generation truth.

### Control Center and observability

The Control Center should show lifecycle state, blockers, false-negative
pressure, gate status, next safe actions and agent/health summaries. The current
Agent Monitor uses derived lifecycle/gate/orchestrator signals; true runtime
agent health remains future work.

## Local and cloud runtime coexistence

JAP is one product across runtime/presentation transports. This repository owns
product semantics; `jap-cloud-based` owns bounded Azure adaptation.

Local WSL/PostgreSQL/WebView2 and Azure PostgreSQL/FastAPI/Container Apps may coexist,
but must share product contracts instead of reimplementing semantics.

The React Control Center is portable across WebView2 and a compatible cloud API.
Cloud succession remains evidence-driven and requires explicit operator approval.

See `../decisions/adr/034_define_shared_jap_product_and_runtime_coexistence.md`.

## Current maturity note

The connector-fleet contract closes discovery-to-recurring-monitoring architecturally,
but implementation still must enforce Candidate -> Connector disposition, due-work
execution and shared fleet health end to end. Adjacent blockers remain discovery
rotation, promotion quality, generic URL/detail evidence and repair/stop taxonomy.

Detailed references live under `../reference/`. Diagrams live in
`system-diagrams.md`.
