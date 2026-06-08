# STOP-002 Stop Taxonomy and Repair Strategy Registry

Status: reference contract
Scope: Search Intelligence stop interpretation, repair planning and Next-Safe-Action routing

## Purpose

STOP-002 defines a shared vocabulary for pipeline stops. A stop is not enough by
itself; the system also needs to know whether the stop is a good fail-closed
boundary, a review boundary, a likely false-negative risk, or a taxonomy gap.

The code contract lives in `src/search_intelligence/stop_taxonomy.py`.
Gate-level classifiers such as `src/search_intelligence/gate_stop_classification.py`
may still decide which category applies, but the meaning of that category and the
safe repair strategy must come from the registry.

## Why this exists

Before STOP-002, several layers interpreted stops independently:

- gate-stop classification;
- EO-002E gate-stop / next-safe-action analysis;
- pipeline stop reassessment;
- Control Center next-safe-action display;
- CLI next-safe-action routing.

That made it too easy for one layer to treat `manual_review_required` as a
terminal stop while another layer saw the same state as a recoverable evidence
gap. STOP-002 does not weaken gates. It makes stops more precise.

## Stop lifecycle classes

| Lifecycle class | Meaning | Default posture |
|---|---|---|
| `not_stop` | No stop-like decision is present. | Continue normal bounded flow. |
| `good_stop` | The stop protects safety, legal or operational boundaries. | Fail closed; no automated retry. |
| `review_stop` | A human or bounded review decision is required. | Do not auto-progress; inspect evidence. |
| `repairable_stop` | The stop may be repaired through a bounded known strategy. | Plan repair under dry-run/apply boundary. |
| `false_negative_risk_stop` | The stop may hide a relevant employer/source because evidence discovery is incomplete. | Prefer bounded evidence/URL discovery over threshold weakening. |
| `taxonomy_gap_stop` | A stop exists but the registry cannot explain it precisely enough. | Fail closed and improve classification before broad reprocessing. |

## Current categories

| Stop category | Lifecycle class | False-negative risk | Repair strategy | Safety zone |
|---|---|---:|---|---|
| `not_stop_like` | `not_stop` | none | `no_repair_not_stop` | SZ0_READ_ONLY |
| `recoverable_url_problem` | `false_negative_risk_stop` | medium | `bounded_source_url_recovery` | SZ1_CANDIDATE_METADATA |
| `technical_reachability_review` | `repairable_stop` | medium | `bounded_source_url_recovery` | SZ1_CANDIDATE_METADATA |
| `terminal_access_risk` | `good_stop` | low | `operator_terminal_override` | SZ2_EVIDENCE_AND_GATES |
| `risk_marker_review` | `review_stop` | medium | `operator_review_triage` | SZ2_EVIDENCE_AND_GATES |
| `detail_discovery_gap` | `false_negative_risk_stop` | high | `bounded_detail_evidence_discovery` | SZ2_EVIDENCE_AND_GATES |
| `weak_relevance_evidence` | `false_negative_risk_stop` | high | `bounded_relevance_evidence_discovery` | SZ2_EVIDENCE_AND_GATES |
| `manual_review_required` | `review_stop` | medium | `operator_review_triage` | SZ2_EVIDENCE_AND_GATES |
| `terminal_unclassified` | `taxonomy_gap_stop` | medium | `taxonomy_review_required` | SZ2_EVIDENCE_AND_GATES |

## Repair strategy rules

Repair strategies are plans, not automatic permission to mutate state.

- SZ0_READ_ONLY strategies may report or display only.
- SZ1_CANDIDATE_METADATA strategies may affect candidate metadata such as a
  selected source URL only through dry-run and explicit apply.
- SZ2_EVIDENCE_AND_GATES strategies may collect bounded evidence or refresh gate
  evidence only through dry-run/apply or explicit operator review.
- No STOP-002 strategy may build connector artifacts, register connectors,
  activate sources, write Bronze/Silver data or change scheduler configuration.

## Good stop vs false-negative stop

A stop is considered good when it protects a real safety, access, policy or data
integrity boundary. Example: confirmed access-denied or bot-defense evidence is a
`terminal_access_risk` and should not be retried automatically.

A stop is considered false-negative-risk when the source may still be relevant,
but the system did not discover enough URL, relevance or detail evidence. Example:
`detail_discovery_gap` should lead to bounded detail-evidence discovery or human
review, not to silently parking the candidate forever.

## Next-Safe-Action relationship

STOP-002 does not replace Next-Safe-Action. It feeds it.

The registry provides:

- `repair_strategy_id`;
- `recommended_next_safe_action`;
- `safety_zone`;
- `human_review_required`;
- dry-run/apply boundary expectations.

Next-Safe-Action may still choose a more conservative UI or CLI action when a
candidate has missing prerequisites or a gate already reached manual-review
state. The registry is the shared interpretation layer; the action runner remains
the execution boundary.

## Implementation surfaces

- `src/search_intelligence/stop_taxonomy.py` — registry and validation helpers.
- `src/search_intelligence/gate_stop_classification.py` — gate evidence to stop category.
- `src/search_intelligence/eo002e_gate_stop_next_safe_analysis.py` — report fields include taxonomy/strategy context.
- `scripts/run_pipeline_stop_reassessment_agent.py` — stop signals carry registry categories.
- `tests/test_stop_taxonomy_registry.py` — registry consistency and contract tests.

## Governance boundary

STOP-002 is intentionally a small reference contract. It must not grow into a
separate governance framework. New categories are allowed when they remove real
ambiguity; otherwise they should be parked until evidence shows a recurring stop
pattern.
