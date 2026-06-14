# EXPAND-005 Parallel Controlled Candidate Expansion Plan

Status: planned implementation bundle
Created from retired restart baseline: `2a669c4 Add controlled candidate creation dry run (#247)`

## Purpose

EXPAND-005 turns the controlled candidate-creation dry-run into a reviewable,
parallel implementation lane without crossing into uncontrolled candidate,
gate, connector, Bronze/Silver/Gold, or scheduler mutation.

The block exists because EXPAND-004 proved that candidate creation can be
previewed safely. The next step is to make that preview useful enough for a
human or later UI workflow to decide which candidates may be created, which
ones must stop, and which assumptions must be validated first.

## System-impact check

| Layer | Expected impact | Boundary |
| --- | --- | --- |
| Discovery | uses existing discovery outputs as inputs only | no external search execution |
| Evidence | classifies and summarizes candidate evidence | no new web crawl by default |
| Candidate/Gate | prepares review/apply boundary | dry-run first, no default writes |
| Connector | records connector candidacy only as future possibility | no activation |
| Bronze/Silver/Gold | reads state for duplicate/context checks | no mutation |
| UI/Observability | prepares review surface and metrics | no direct mutation button without dialog/audit |
| Scheduler | none | no scheduler change |
| Docs/Tests | adds explicit contracts and targeted checks | full validation required before PR |

## Parallel lanes

These lanes may be implemented in parallel because they share a read-only input
boundary and fan in only at validation/report level.

### Lane A — EXPAND-005A Candidate creation evidence review

Goal: produce a deterministic, DB-backed review report for candidates that the
EXPAND-004 dry-run would create.

Expected outputs:

- selected candidate seed records
- candidate identity key and normalization rationale
- source of signal and provenance
- evidence completeness class
- duplicate/known-company risk
- stop/review reason if not ready
- recommendation: `create_candidate_ready`, `manual_review_required`,
  `insufficient_evidence`, `duplicate_or_known_company`, `stop`

Boundary:

- read-only by default
- no candidate insert
- no gate decision
- no source activation
- no connector artifact generation

### Lane B — EXPAND-005B Genericity proof matrix

Goal: show whether the candidate-creation logic is transferable beyond the few
known examples.

Expected outputs:

- sampled companies grouped by signal origin
- pass/fail/needs-review by generic criterion
- false-positive risk and false-negative risk notes
- assumptions that must move to ASSUMPTION-001 before use as decision truth
- score contribution to `Generik operativ`

Genericity criteria:

- company identity can be resolved without employer-specific hardcoding
- source URL evidence is concrete enough for next-stage review
- duplicate interpretation is explainable
- remote/Hannover relevance is evidence-backed or explicitly unknown
- stop reasons are reusable categories, not ad-hoc text
- recommendation does not rely on prior favoritism

### Lane C — EXPAND-005C Apply boundary design

Goal: define the safe transition from review report to a future controlled
candidate insert.

Expected boundary:

- `--dry-run` remains default
- `--apply` must require explicit CLI flag and visible selected target set
- active-controlled sources are excluded unless explicitly opted in
- all writes are audit/provenance-linked
- no scheduler or connector activation side effects
- no literal `None`/`null` URL values
- every insert must be reproducible from DB-backed evidence, not CSV/Excel input

### Lane D — UI-001A Approval-safe review-action foundation

Goal: prepare the GUI direction without implementing unsafe click-to-mutate
behavior prematurely.

Expected design:

- review dialog before mutation
- visible evidence, boundary, and expected result
- explicit confirmation
- audit/event write through existing safe service path only
- no direct SQL in templates or handlers
- no hidden activation, scheduler, connector, Bronze/Silver/Gold side effects

### Lane E — AGENT-001A Derived vs runtime agent health clarification

Goal: keep the Agent Monitor honest while preparing a later real agent-health
model.

Expected outputs:

- label current cards as derived lifecycle/gate/orchestrator status where needed
- use gate-review history for historical healthy signals when available
- keep true runtime health separate until a dedicated agent-observability model
  exists

## Fan-in validation

Before commit/PR:

```bash
python -m pytest -q <targeted-tests-for-touched-surfaces>
python scripts/run_validate001_unified_validation.py --profile commit
git diff --check
git status --short
```

Expected targeted tests depend on implementation scope. At minimum:

- dry-run report contract tests for EXPAND-005A
- genericity scoring/classification tests for EXPAND-005B
- apply-boundary safety tests for EXPAND-005C if any write path is introduced
- UI/view-model tests for UI-001A if templates or view models are touched
- agent-monitor classification tests for AGENT-001A if Control Center logic is
  touched

## Non-goals

- no candidate creation by default
- no source or connector activation
- no scheduler changes
- no external acquisition execution
- no CSV/Excel as pipeline input
- no broad UI redesign
- no Kafka/Spark/cloud migration work
