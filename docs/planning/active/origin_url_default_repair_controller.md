# Origin URL Default Repair Controller

Status: implemented for review  
Risk: R2 bounded external-read and provider-review path  
Product role: mandatory Origin URL resolution before connector work

## Product requirement

The URL Finder is a critical dependency of Product V1. A single deterministic
`not_found` result is not a terminal result and must not silently remove an
employer from the product chain.

The product-default state machine is:

```text
employer-origin candidate with unresolved URL
→ deterministic URL generation and bounded HTTP probing
→ if unresolved: bounded Tavily search and deterministic probing
→ if unresolved: deeper page/evidence grading of observed candidates
→ if ambiguous and eligible: one bounded gpt-5.4-mini adjudication
→ deterministic selected URL, operator review, explicit configuration blocker,
  or repair_exhausted after the complete cascade
```

Company identity affects evidence only. It does not select a separate algorithm,
threshold, provider, connector implementation, or exception path.

## Default integration

The complete cascade is now the default for:

- `scripts.run_eo002b_url_finder_validation`;
- `scripts.run_cand001_validated_origin_url_persistence_gate`;
- direct product validation through `scripts.run_origin_url_default_repair`.

The original single-pass discovery function remains available only as an atomic
stage and explicit diagnostic path. It is not the product default.

## Provider and cost envelope

Per employer, defaults are bounded to:

- at most four Tavily queries;
- at most five results per query;
- at most twelve generated URL candidates per URL-Finder pass;
- at most four candidates for deep evidence grading;
- at most twelve evidence HTTP requests;
- at most one `gpt-5.4-mini` adjudication;
- pessimistic LLM cost reservation no greater than USD 0.01 per employer.

A missing Tavily key, missing OpenAI key, unknown model price, exceeded cost
reservation, or provider failure is not reported as ordinary `not_found`. It is
an explicit repair/configuration blocker.

## LLM boundary

The LLM receives only observed and deterministically assessed candidate IDs. It
may:

- confirm deterministic evidence;
- prefer another already observed candidate;
- require manual review;
- abstain.

It may not:

- invent a URL;
- cite a candidate outside the evidence packet;
- persist a URL;
- change a gate;
- register or activate a connector/source;
- write Bronze/Silver jobs;
- change ranking or scheduling.

An LLM recommendation remains an operator-review signal. Only a deterministic
A/B-tier selection may enter the existing explicit CAND-001 persistence gate.

## Terminal states

- `selected_deterministic_baseline`
- `selected_tavily_repair`
- `selected_evidence_and_llm_repair`
- `operator_review_required`
- `repair_configuration_blocked`
- `repair_exhausted`

`repair_exhausted` is valid only after all applicable stages ran within their
budgets. It means the case remains unresolved, not that the employer has no
origin source and not that the employer should be discarded.

## 1&1 acceptance case

Observed before this change:

- deterministic baseline: Tier D / `not_found`;
- Tavily advanced search: Tier D / `not_found`, confidence 0.650;
- no automatic evidence regrading;
- no automatic LLM eligibility decision;
- no explicit full-repair terminal state.

After merge, the default runner must continue automatically from the Tavily
result into evidence regrading and, when eligible and configured, the bounded
LLM stage. Its output must show every stage, request count, blocker, and final
state.

## Exit gate

This block is complete when:

1. full CI, Ruff, governance, and frontend checks pass;
2. EO-002B uses the repair cascade without extra provider flags;
3. CAND-001 cannot apply from the legacy single-pass diagnostic path;
4. missing provider configuration is explicit;
5. LLM recommendations cannot become persisted URL truth;
6. the live 1&1 acceptance run shows the complete repair trace;
7. the Product E2E audit is rerun after any approved URL persistence.
