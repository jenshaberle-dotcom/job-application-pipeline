# Active Planning

Status: active planning surface

Keep this folder small. A planning artifact belongs here only while it is still
an active steering input. When the implementation or decision is finished, move
it to `../../archive/planning/` or promote the stable rule into `../current/`,
`../reference/`, or `../decisions/`.

Current active anchors:

- `roadmap.md`

<!-- PLAN-001-ACTIVE-README-START -->
## Future readiness and assumption governance

- `future_readiness_and_assumption_governance.md` defines the active planning
  premise for cloud/event transition readiness, manual market observation,
  simplification validation and White-Whale triage.
<!-- PLAN-001-ACTIVE-README-END -->

<!-- REFACTOR-001-ACTIVE-README-START -->
## REFACTOR-001 Architecture & Runtime Refactor Campaign

- `refactor001_architecture_runtime_refactor_campaign.md` is the planned
  refactor gate after GENERIC/EXPAND evidence closure and a minimal controlled
  V1 proof path, but before cloud migration, Kafka/event backbone, Spark or
  serious productionization.
<!-- REFACTOR-001-ACTIVE-README-END -->

<!-- FREEZE-002-ACTIVE-README-START -->
## FREEZE-002 Pipeline Maturity to V1 Campaign

- `freeze002_pipeline_maturity_to_v1_campaign.md` defines the second freeze
  campaign for raising remaining pipeline areas toward >=90% while preserving a
  usable V1 path with GUI before cloud or streaming expansion.
<!-- FREEZE-002-ACTIVE-README-END -->

<!-- STRATEGIC-SEQUENCING-GENERICS-FIRST-START -->

## Strategic sequencing: generics before V1

Status: active planning baseline.

The current strategic order is:

1. Finish the generics proof cleanly.
2. Open controlled candidate creation only through a reviewed apply gate.
3. Make the review UI usable with approval-safe actions.
4. Build matching, Gold decision views, and the first useful V1 product flow.
5. Run the large architecture and runtime refactor campaign after V1.
6. Build Defect Management after V1 and after the refactor campaign.
7. Continue Agent/Ops, Cloud readiness, and later Kafka/Streaming after the core path is mature.

### Resolved planning decisions

- Generics proof is prioritized over Product V1.
- Product V1 is intentionally postponed until the generics/provider evidence path is clean.
- Mutating UI actions must not be built before the backend apply boundary exists.
- Matching and Top-N job logic may be prepared read-only, but should not drive a V1 promise before Apply Gate and Review UI are ready.
- Defect Management remains important but is sequenced after V1.
- The large refactor campaign is explicitly placed after V1 and before Defect Management.
- Cloud and Kafka/Streaming remain later tracks; current work should stay event-ready but not event-driven.

### Current ordered roadmap

| Order | Work item | Purpose | Boundary |
|---:|---|---|---|
| 0 | Post-merge state check | Confirm current HEAD, validation, and Block-Z state | Read-only |
| 1 | PROVIDER-001B Read-only Provider Evidence Discovery | Find provider-backed origin evidence from existing DB/code/url/source signals | No external probes by default |
| 2 | PROVIDER-001C Provider Coverage Decision Bundle | Close or explicitly justify the provider-backed origin coverage gap | Review output only |
| 3 | GENERIC final recheck | Re-run GENERIC-005 / EXPAND-008 after provider evidence | No candidate mutation |
| 4 | COMPLIANCE-001A Probe Boundary Matrix | Define safe boundaries before any external provider/source probe | Required before external probes |
| 5 | APPLY-001A/B/C Controlled Candidate Creation Apply Gate | Move from blocked dry-run to reviewed, audited candidate creation | No activation by default |
| 6 | UI-001/002 Review Queue and Approval-safe Actions | Make Review Required / Ready / Active / Parked usable | UI actions require backend apply boundary |
| 7 | MATCH-001 Jens Fit Scoring | Score jobs by remote, travel, salary, 35h, data-role signal, fallback roles | Read-only scoring first |
| 8 | GOLD-001 Top-N Decision Layer | Produce Top-N / Top-5 candidates with reason codes | No auto-apply |
| 9 | DOCGEN-001 + V1-001 | Generate CV/application-letter scaffolds and first useful end-to-end flow | Human review required |
| 10 | REFACTOR-001 Architecture and Runtime Refactor Campaign | Clean module boundaries, runtime boundaries, cloud/event readiness | After V1, before Defect Management |
| 11 | DEFECT-001 Defect Management Foundation | Track defects, root causes, recurrence guards, and verification | After V1 and refactor |
| 12 | AGENT/OPS Health | Runtime/source/agent health and observability | After core product path |
| 13 | CLOUD-001 | Cloud-ready batch deployment path | After core/V1/refactor |
| 14 | STREAM-001 Kafka/Event Backbone | Event streaming, Kafka, possible Spark later | Later, not Freeze Path |

### Backlog alignment

- Keep PROVIDER-001B/C as the next main block.
- Keep APPLY-001 before mutating UI actions.
- Keep UI Review Queue before V1 product flow.
- Keep MATCH-001, GOLD-001, DOCGEN-001, and V1-001 as the product-value path.
- Keep REFACTOR-001 visible and explicitly after V1.
- Keep DEFECT-001 after V1 and REFACTOR-001.
- Keep Agent Capability, Ops Health, Cloud, Kafka, Spark, and MCP as later tracks unless a concrete blocker appears.
- Continue using curated output bundles and run-scoped validation outputs as review artifacts only, never as pipeline inputs.

<!-- STRATEGIC-SEQUENCING-GENERICS-FIRST-END -->

<!-- PROVIDER-001-ACTIVE-README-START -->

## PROVIDER-001 Provider Evidence Closure

- `provider001_provider_evidence_closure.md` defines the active provider evidence
  closure path for the generics-first sequence before APPLY-001 and V1.

<!-- PROVIDER-001-ACTIVE-README-END -->

<!-- MCP-001-ACTIVE-README-START -->

## MCP-001 Engineering Assistance / Governance Tooling

- `mcp001_engineering_assistance_governance_tooling.md` places MCP-001A after Generik and Safe-Apply/Gate stabilization, before the full Product V1 phase, with read-only-first engineering-assistance boundaries.

<!-- MCP-001-ACTIVE-README-END -->
