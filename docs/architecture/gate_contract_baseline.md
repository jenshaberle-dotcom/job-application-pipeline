# Gate Contract Baseline

Status: active architecture contract
Scope: all Search Intelligence gates

## Purpose

A gate is not only a stop. A gate is a diagnosis contract.

Every gate must explain what it saw, why it decided, what risk remains and what the next safe action is.

## Required gate fields

| Field | Meaning |
|---|---|
| gate_name | stable gate identifier |
| candidate_id | candidate being evaluated |
| input_evidence_refs | evidence rows, reports, URLs or run IDs used by the gate |
| decision | pass, stop, manual_review_required, approve, reject or similar |
| decision_confidence | confidence in the decision, not necessarily in a selected URL |
| risk_level | low, medium, high or critical |
| stop_reason | human-readable reason when not passed |
| next_safe_action | bounded next step that is allowed |
| manual_override_path | how a human can override or continue safely |
| audit_event_ref | event or report that explains the decision later |

## Gate inventory

| Gate | Current maturity | Main gap |
|---|---:|---|
| Candidate Promotion / Türsteher | 42/100 | not explainable enough; downstream outcomes not yet measured |
| Origin URL Gate | 62/100 before broader validation | improved by EO-002D, but sample size is small |
| Aggregator Rejection Gate | 75/100 | strong rule, needs better user-facing explanations |
| Detail Evidence Gate | 38/100 | likely next major bottleneck |
| Connector Feasibility Gate | 55/100 | depends on stronger detail evidence |
| Connector Validation Gate | 60/100 | needs better historical gate visibility |
| Final Approval Gate | 70/100 | conceptually strong, still needs operational UI polish |
| Reset/Reprocess Gate | 58/100 | dry-run behavior is good; UI and state-machine integration missing |
| Deactivation/Removal Gate | 25/100 | recognized requirement, not yet implemented |

## Rule for future gate work

Do not weaken a gate because a candidate is stuck. First identify whether the stop is caused by URL discovery, evidence discovery, missing gate context, candidate promotion, connector feasibility or security policy.
