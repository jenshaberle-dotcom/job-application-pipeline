# PLAN-001 Future Readiness and Assumption Governance

Scope: Planning, governance and documentation guardrail. This document does not
introduce Kafka, Spark, cloud infrastructure, database migrations, scheduler
changes, connector behavior, candidate promotion logic, or Bronze/Silver/Gold
mutation.

## Purpose

PLAN-001 prevents future architecture and governance drift around four related
planning tracks:

1. Cloud/event/Kafka/Spark transition readiness.
2. Manual market observation as a controlled benchmark-like reality check.
3. Validation of simplifications and assumptions before they become decision truth.
4. White-Whale backlog triage so valuable but oversized ideas are parked without
   silently changing the active Freeze Path.

The premise is:

> Build event-capable, but not event-driven yet.

The project remains local-first and batch-oriented until the core pipeline reaches
more than 90 percent maturity. Current work should nevertheless avoid decisions
that would make a later cloud or event transition unnecessarily expensive.

## Future platform transition path

The intended sequence is:

1. Core Pipeline >90% maturity.
2. Cloud-ready Batch Pipeline / Cloud Readiness.
3. DB-backed Outbox/Event Foundation.
4. Kafka Event Backbone.
5. Spark Analytics / Replay / Feature Layer, only if real analytical value exists.

Kafka is the preferred later event backbone because it is a realistic and
recognizable event-streaming technology for the target data-engineering and
automotive context. Spark is a later analytics/replay/feature-computation option,
not a resume-driven mandatory component.

## Near-term engineering guardrails

Until the platform transition becomes active implementation work, new pipeline
work should prepare the transition by keeping the following properties visible:

- stable IDs for jobs, companies, profiles, candidates, reviews and decisions,
- clear timestamps such as observed_at, occurred_at, recorded_at and processed_at,
- auditability for decisions and manual overrides,
- idempotent processing and safe reprocessing assumptions,
- no CSV, Excel, Markdown or JSON export artifact as hidden pipeline input,
- event vocabulary that describes domain changes even before Kafka exists,
- outbox-ready boundaries around future event-producing decisions,
- no local-only assumptions that would block cloud, CI or managed scheduler use.

Reports and exports may explain decisions for humans. They must not become hidden
sources of truth for operational execution, activation gates, destructive actions,
cloud migration, Kafka publication or Spark analytics.

## MARKET-003 Manual Market Observation

Manual market observation is the controlled replacement for ad-hoc benchmark-like
chat lists or external feed impressions.

Manual observations may include LinkedIn, XING, Indeed, recruiter messages, job
fair notes, personal research, company career-page sightings or other manually
observed market signals. These observations are valuable because they expose
potential false negatives and market blind spots. They are not automatically
truth, not a source connector and not a gate decision.

A future MARKET-003 implementation should persist manual observations with at
least:

- observed_at,
- observer or origin label,
- source surface such as LinkedIn, XING, Indeed, recruiter or manual research,
- raw company name and optional normalized company candidate,
- observed role/title or signal text,
- URL or evidence reference where available,
- relationship to known companies, candidates or silver jobs where measurable,
- review status,
- whether the observation is allowed only as recall/blind-spot signal or may
  trigger a bounded downstream discovery action.

Manual observations may start discovery or recall analysis. They are not a pipeline input
and must not silently become source-of-truth inputs for gates, Gold metrics,
dashboards or connector activation.

<!-- MARKET-003A-COMPANY-SEED-START -->
## MARKET-003A Manual Company Observation Seed Register

This planning anchor preserves the manually observed company group-by work as a
review seed for MARKET-003 and ASSUMPTION-001. It is intentionally not a pipeline
input, not source-of-truth, not automatically truth, not a gate pass, not a Gold metric and not an automatic origin-candidate creation list.

Manual company observations may later be persisted in a DB-backed MARKET-003
model. Until then, the following seed groups preserve recall/blind-spot context
and normalization risks discovered during manual market review.

### Seed group A: already visible or known in pipeline context

| Company seed | Current interpretation | Review note |
|---|---|---|
| HDI | known company / origin-source context | Keep as known baseline for origin-source validation and scheduler/connector learning. |
| VHV | known company / origin-source context | Keep as known baseline; prior source URL recovery uncertainty remains useful. |
| adesso | known company / market signal | Useful for StepStone/origin mirroring and relevance vocabulary checks. |
| E.ON Grid Solutions | known company / market signal | Useful for external market recall and source discovery checks. |
| NEW YORKER | known company / market signal | Useful as known-company suppression and recall baseline. |
| Finanz Informatik | active employer-origin reference | Milestone/template for employer-origin connector governance. |
| Rossmann | known/reserve-style source context | Keep for future source/candidate comparison. |
| enercity | known origin-source/connector context | Keep for source lifecycle and cloud/platform vocabulary examples. |

### Seed group B: manually observed attractive or missing companies

| Company seed | Current interpretation | Review note |
|---|---|---|
| Bahlsen | manually observed / potentially missing | Check whether pipeline discovers it through current sensors or origin-source discovery. |
| GETEC | manually observed / potentially missing | Validate company identity and relevant data/IT roles before candidate promotion. |
| MEDIFOX DAN | manually observed / potentially missing | Validate naming and origin-source evidence before treating as a missed company. |
| goetel | manually observed / potentially missing | Validate naming, region relevance and origin-source presence. |
| Dataciders | manually observed / potentially missing | Strong data/analytics signal; preserve as recall/blind-spot seed. |
| Atos | manually observed / potentially missing | Validate local/remote relevance and source family before conclusions. |
| Sopra Steria | manually observed / potentially missing | Validate consulting/source-role ambiguity before promotion. |
| QUNIS | manually observed / potentially missing | Strong BI/analytics signal; preserve as recall/blind-spot seed. |

### Seed group C: additional group-by company seeds from manual review

| Company seed | Current interpretation | Review note |
|---|---|---|
| VALUE AG | manually observed company seed | Keep as raw seed; validate identity before normalization or candidate decisions. |
| SVA | manually observed company seed | Ambiguous abbreviation risk; validate exact employer identity. |
| ivv | manually observed company seed | Normalize carefully; raw spelling may not equal canonical employer identity. |
| NETGO | manually observed company seed | Validate exact brand/legal entity and role relevance. |
| SPARETECH | manually observed company seed | Validate market relevance and origin-source evidence. |
| Thinkport | manually observed company seed | Validate exact company identity and relevant roles. |
| NeoBIM | manually observed company seed | Validate domain relevance before candidate promotion. |
| Oviva | manually observed company seed | Validate location/remote relevance and source evidence. |
| Aignostics | manually observed company seed | Validate location/remote and role fit before downstream use. |
| Veeva Systems | manually observed company seed | Validate Germany/remote relevance and role fit. |
| Grafana Labs | manually observed company seed | Validate remote/location and role relevance; likely remote/global context. |
| Concordia Versicherungen | manually observed company seed | Validate Hannover/regional relevance and origin-source evidence. |
| EEW Energy from Waste | manually observed company seed | Validate data/IT role relevance and origin-source evidence. |
| ISR Information Products | observed through BA duplicate provenance | Preserve as BA overlap/source-quality learning signal, not just duplicate noise. |

### Governance rule

Manual company group-by output is recall and blind-spot evidence. Normalized
company identity, same-company assumptions, LinkedIn-only conclusions,
aggregator-only conclusions and origin-source conclusions remain assumptions until
validated. They may start bounded discovery but must not become gate, Gold,
dashboard or connector-activation truth without evidence.
<!-- MARKET-003A-COMPANY-SEED-END -->

## ASSUMPTION-001 Simplification Validation Register

The project intentionally uses heuristics to start discovery, but unvalidated
simplifications must not become decision truth without evidence.

A future ASSUMPTION-001 register should track simplifications such as:

- company-name normalization and company equivalence,
- employer-origin identity,
- duplicate interpretation,
- remote/hybrid signal quality,
- source-family classification,
- relevance/title matching,
- StepStone mirroring assumptions,
- LinkedIn-only, aggregator-only or origin-only conclusions,
- inferred source value from small samples.

Each registered assumption should include:

- assumption statement,
- risk type such as false positive, false negative, compliance or operational,
- evidence required,
- validation method,
- current confidence,
- review status,
- expiry or recheck trigger,
- allowed usage: discovery_only, gate_allowed, gold_allowed or dashboard_allowed.

Rule:

> Heuristics may start discovery, but unvalidated simplifications must not become
> gate, Gold, dashboard or product truth without evidence.

## WHALE-001 White-Whale Backlog Triage

The White-Whale backlog is a parking and triage surface, not a hidden active
roadmap. Valuable oversized ideas should be classified so they are preserved
without distorting the Freeze Path.

Suggested categories:

1. Freeze-compatible now.
2. Soon after core maturity.
3. After cloud readiness.
4. After outbox/Kafka foundation.
5. Only if measurable value is proven.
6. Rejected or intentionally parked as too much whale.

Examples:

- MCP Project State Server: later, read-only-first governance tooling.
- Kafka Event Backbone: after cloud-ready batch and DB outbox.
- Spark Analytics Layer: after event/history foundation and only with real
  analytics, replay or feature-computation value.
- Defect Management Foundation: important but scheduled behind current maturity
  and source/search-intelligence work.
- Agent health and Control Center maturity: product/observability follow-up.
- Sustainability and lifecycle KPIs: later governance/compliance maturity.

## Intended next sequencing

After SENSOR-001 is closed by scheduler validation, the recommended planning
sequence is:

1. Keep PLAN-001 as this governance anchor.
2. Implement MARKET-003 as a DB-backed manual market observation foundation.
3. Implement ASSUMPTION-001 as the simplification validation register.
4. Continue MARKET-002A / STEPSTONE-002A discovery-quality review with company
   and recall focus.
5. Continue EO-003 / candidate promotion quality only with measured downstream
   outcomes and explicit assumption boundaries.

## Non-goals

PLAN-001 does not authorize:

- adding Kafka or Spark dependencies now,
- replacing the batch pipeline with streaming,
- moving infrastructure to cloud before core maturity,
- turning manual observations into operational inputs,
- weakening gates based on unvalidated assumptions,
- expanding the White-Whale backlog into active scope without explicit triage.
