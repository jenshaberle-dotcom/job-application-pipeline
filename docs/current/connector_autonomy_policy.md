# Validated Connector Autonomy A1

Status: approved operator policy  
Approved by: Jens  
Approved at: 2026-08-04 20:10 Europe/Berlin  
Policy version: `connector-autonomy-a1-2026-08-04`

## Decision

The pipeline may gradually receive autonomy. The first level is deliberately narrow:
validated connectors may be registered and, after a separate exact readiness proof,
connected as controlled sources without asking Jens for a new per-connector approval
token.

This is standing authority, not broad self-direction.

## A1 sequence

```text
connector implementation
→ connector_validation_gate = passed / ready_for_final_approval
→ standing A1 registration authorization
→ connector registration through reviewed code and green CI
→ generic activation-readiness preview
→ activation_readiness_supported exactly
→ separate controlled activation change
→ one bounded first-ingestion proof
→ observe and reassess before any higher autonomy level
```

## Allowed

A1 may authorize:

- connector registration after the existing connector-validation gate passes;
- a separately reviewed controlled source activation only when the generic readiness
  outcome is exactly `activation_readiness_supported`;
- one bounded first-ingestion proof under an explicit apply path;
- the existing audited candidate/source lifecycle transitions required by those
  actions.

The exact legacy approval token remains available as a fallback when A1 is paused,
missing or revoked.

## Mandatory stops

A1 must stop when any of the following applies:

- connector validation is missing, failed or not `ready_for_final_approval`;
- activation readiness is anything other than exactly
  `activation_readiness_supported`;
- the readiness result includes manual overlap review, unknown evidence, unavailable
  database evidence or non-job preview records;
- connector execution would require browser challenge or access-control bypass;
- an unapproved provider request would be required;
- the requested action would change scheduling, enable recurring ingestion, mutate
  ranking or scores, generate an application or submit an application.

A correct stop is a successful governance outcome, not an implementation failure.

## Runtime authority

Migration `085_create_validated_connector_autonomy_a1.sql` stores the policy as DB
truth. The final approval gate may use it only when every fail-closed A1 boundary is
present and the connector-validation gate has passed.

The approval evidence records:

- authorization mode;
- policy key and policy version;
- standing authorizer;
- candidate and source identity;
- forbidden side effects.

Authorization events are append-only audit evidence. Pausing or revoking the policy
restores the exact legacy token requirement without weakening validation.

## Still operator-owned or separately gated

A1 does not authorize:

- autonomous discovery-to-activation loops;
- scheduler integration or recurring execution;
- provider or LLM autonomy;
- assessment or ranking decisions;
- application-draft generation or submission;
- expansion to A2 or a broader risk envelope.

## Promotion rule

A higher autonomy level may be proposed only after repeated A1 executions show:

- stable validation and first-ingestion outcomes;
- correct stops for ambiguous cases;
- complete audit evidence;
- reversible or pausable operational state;
- no boundary drift.
