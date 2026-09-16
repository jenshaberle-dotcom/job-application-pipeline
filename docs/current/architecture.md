# Current System Architecture

Status: current truth
Scope: product-level architecture after DOC-001M

## Architecture in one sentence

Market signals are treated as weak evidence until they pass bounded discovery,
origin/detail evidence checks, explicit gates and controlled approval paths.
Only then can a source become operational input for Bronze/Silver/Gold and the
Control Center.

```text
Market Sensors
  -> Candidate / Source Discovery
  -> URL / Origin / Detail Evidence
  -> Gates and Stopper Reassessment
  -> Connector Candidate / Build / Validation / Approval
  -> Active Controlled Source
  -> Bronze / Silver / Gold / Control Center
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

Market sensors and aggregators discover companies, source targets and search
spaces. They are intentionally bounded and defensive. Aggregators are discovery
inputs, not canonical source truth.

### Candidate and origin discovery

Candidate discovery turns signals into employer-origin candidates. Candidate
identity, source URL evidence and duplicate handling are safety concerns: missing
URLs stay missing, and ambiguous candidates must not be pushed through the
pipeline as if they were validated.

### Detail evidence and gates

Origin/detail evidence is required before connector work. Gates decide whether
evidence is enough to progress. Stops must include a reason, next safe action and
a manual-review path.

### Connector path

Connector candidacy, artifact generation, validation, registration planning,
final approval and active controlled operation are separate stages. Connector
artifacts are not activation.

### Job data layers

- Bronze keeps bounded raw acquisition and lineage.
- Silver builds canonical job representation and quality filtering.
- Gold provides decision, observability and Control Center read models.

### Control Center and observability

The Control Center should show lifecycle state, blockers, false-negative
pressure, gate status, next safe actions and agent/health summaries. The current
Agent Monitor uses derived lifecycle/gate/orchestrator signals; true runtime
agent health remains future work.

## Local and cloud runtime coexistence

JAP is one product with multiple runtime and presentation transports. This
repository remains the current upstream authority for product/domain semantics;
`jap-cloud-based` owns bounded Azure adaptation and cloud-runtime concerns.

The local WSL/PostgreSQL/WebView2 runtime and the Azure
PostgreSQL/FastAPI/Container-Apps runtime may coexist for as long as that is
useful. They must converge on shared product contracts rather than independently
reimplement ranking, gates, Top-5, application or data-layer semantics.

The React Control Center is a portable product surface: WebView2 is one local
presentation shell, while the same product UI may later run in a browser against
a compatible cloud API. Cloud succession is evidence-driven and requires an
explicit operator decision; a working cloud demo does not retire local JAP.

See `../decisions/adr/034_define_shared_jap_product_and_runtime_coexistence.md`.

## Current maturity note

The documentation structure is now stable enough for product work again, but the
pipeline itself is not closed-loop yet. The biggest product blockers remain
StepStone discovery rotation, candidate promotion quality, URL/detail evidence
generics and repair/stop taxonomy.

Detailed references live under `../reference/`. Diagrams live in
`system-diagrams.md`.
