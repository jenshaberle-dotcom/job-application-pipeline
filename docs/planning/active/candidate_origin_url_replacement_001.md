# CANDIDATE-ORIGIN-URL-REPLACEMENT-001

Status: implementation validation  
Issue: #395  
Parent runtime acceptance: #392  
Completed prerequisite: #393 / PR #394

## Runtime evidence

Fresh exact S7N no-write probes on
`main@e071843dbb9318d3184c4c84f38785ef7cbb8409` produced two live repair
candidates:

- `57:accompio`: current `https://www.accompio.com/de/karriere/` →
  proposed `https://karriere.accompio.com/de`;
- `23:computacenter`: current `https://jobs.computacenter.com/` →
  proposed
  `https://jobs.computacenter.com/search/?searchby=location&q=&locationsearch=&geolocation=&optionsFacetsDD_country=&optionsFacetsDD_city=`.

Both probes returned HTTP 200, persisted no feasibility review and left all
candidate/review counts unchanged.

## Existing boundary

CAND-001 owns initial candidate URL persistence only. It intentionally blocks a
different selected URL when `candidate_url` is already populated and its SQL
updates only null or blank values.

S7N owns bounded feasibility evidence. Its `--write` mode persists a feasibility
review; it does not own candidate URL replacement.

The new gate fills only that missing transition.

## Transition

```text
exact target + exact expected previous URL + proposed URL
→ load current DB candidate
→ fresh bounded S7N probe of current URL
→ exact live repair-candidate match
→ dry-run replacement plan
→ exact operator approval token + complete approved-target coverage
→ one transaction:
     audit insert
     exact compare-and-set candidate update
→ idempotent replay
→ fresh S7N and Product E2E bridge evidence
```

## CLI contract

Each requested repair uses one quoted value:

```text
candidate_id:company_key|expected_previous_url|proposed_url
```

Dry-run is the default.

Apply requires:

```text
--apply
--approval-token approve_candidate_origin_url_replacement
--approved-target candidate_id:company_key
```

The approved-target set must exactly equal the requested target set. Duplicate
targets and partial coverage fail closed.

## Live evidence contract

Planning is allowed only when the active S7N runtime returns:

```text
blocker_code=origin_url_repair_candidate_detected
```

and its `repair_candidate_url` conservatively normalizes to the exact proposed
URL.

Previous console output, JSON, Markdown, web research and manually copied reports
are not pipeline inputs. They may explain why the gate is run, but the decision
uses current DB state plus a new bounded HTTP probe.

## Replacement decision

A ready plan uses:

```text
decision=replace_validated_candidate_url
status=operator_decision_required
apply_allowed=true
```

An applied audit row uses:

```text
selected_url_source=live_s7n_repair_candidate
decision=replace_validated_candidate_url
review_status=applied
```

Migration `089_add_candidate_origin_url_replacement_decision.sql` extends the
existing CAND-001 audit-table decision constraint and preserves the Gold history
view.

## Compare-and-set boundary

Apply updates exactly one row only when all values still match:

- candidate ID;
- company key;
- current URL observed under the transaction;
- status is not `active_controlled`.

Audit insert and candidate update share the same transaction. A zero-row or
multi-row update aborts the transaction.

## Idempotency

When the candidate already stores the exact proposed URL, the result is:

```text
decision=no_action_already_replaced
status=passed
```

No second audit or candidate mutation is created. A multi-target apply must be
either entirely replacement-ready or entirely idempotent; mixed or blocked sets
fail closed.

## Boundaries

The gate has no authority for:

- provider or LLM requests;
- feasibility-review persistence;
- connector generation, registration or source activation;
- Bronze, Silver or Gold job writes;
- scheduler or Wave changes;
- assessment, ranking, Top-5, Candidate Fact or application mutation;
- company-specific branching or URL allowlists;
- automatic replacement from S7N alone.

## Acceptance

- migration contract and direct unit tests pass;
- full Pipeline CI and React build pass;
- private DB-backed dry-run evaluates both exact targets without mutation;
- any apply remains a separate explicit operator decision;
- applied rows are verified through candidate state and audit history;
- exact replay is idempotent;
- refreshed S7N and connector-build bridge runs select the next Product V1
  transition from current evidence.
