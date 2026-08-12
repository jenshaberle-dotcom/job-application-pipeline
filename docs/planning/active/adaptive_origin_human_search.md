# Adaptive Origin Human-Search Runtime

Status: implemented for validation  
Risk: R2 bounded external-read and provider-hypothesis path  
Product role: mandatory origin discovery repair after literal baseline failure

## Trigger

The original 1&1 acceptance case demonstrated a product false negative and led to
the first finite adaptive search automaton. A later all-candidate reality audit
showed that provider-free diagnosis alone was not representative of the real
recovery path.

The current ordering is based on fresh runtime evidence from the live candidate
portfolio:

- 27 current candidates were missing an origin URL;
- unchanged deterministic origin validation recovered 10/27;
- on the remaining 17 deterministic misses, a paired no-Tavily benchmark produced
  8/17 deterministically valid direct origins from `gpt-5.4-mini` and 12/17 from
  `gpt-5.5`;
- the model union recovered 13/17 because Mini had one unique validated success
  that 5.5 missed;
- combined pre-Tavily potential is therefore 23/27 (85.19%) on that observed
  portfolio;
- Tavily free-plan usage subsequently reached 999/1000 with PAYG remaining zero.

The evidence therefore does not support either Tavily-first search or replacing
Mini outright with the stronger model.

## Product decision

The default URL finder remains a finite adaptive search automaton, but expensive
search moves behind the two bounded direct-model stages:

```text
deterministic baseline
→ symbol-aware brand and operator URL hypotheses
→ gpt-5.4-mini direct URL hypotheses
→ deterministic validation of Mini URLs
→ on miss: gpt-5.5 direct URL hypothesis escalation
→ deterministic validation of escalation URLs
→ on both misses: residual Tavily search
   - novel model query hypotheses first
   - remaining deterministic human-search queries second
   - bounded site/domain follow-up last
→ deep evidence grading
→ one late LLM evidence adjudication when eligible
→ selected URL, operator review, configuration blocker, or repair exhausted
```

The model and Tavily stages have deliberately different authority:

- primary Mini stage: at most three novel search queries and three novel HTTPS URL
  hypotheses;
- 5.5 escalation stage: the same bounded shape, with the shared anti-repeat ledger
  removing hypotheses already proposed by Mini;
- model query hypotheses are deferred search inputs only and cannot establish
  origin truth;
- every direct model URL is independently fetched and validated by the unchanged
  company-identity, career-origin and URL-policy gates before it may be selected;
- Tavily is a residual evidence-acquisition stage only after both direct-model
  stages fail to select;
- late LLM: choose, abstain, or request review among already observed deep evidence;
- no LLM or search provider may persist a URL, register a connector, activate a
  source, write Bronze/Silver data, change ranking, or change scheduling.

## Anti-repetition contract

Every provider transition must add at least one of:

- a novel normalized query;
- a novel normalized URL;
- a newly observed non-aggregator domain;
- a changed discovery-state fingerprint.

Queries and URLs are normalized and stored in one per-employer
`SearchProgressLedger`. Mini hypotheses enter that ledger before 5.5 is called, so
5.5 cannot repeat them. Both model query sets enter the same ledger before residual
Tavily search and duplicate query hypotheses are therefore executed at most once.
Discovery state is fingerprinted from decision, confidence and observed URLs. A
repeated fingerprint records no progress and cannot create an unbounded provider
loop.

The runtime has no unbounded loop. Maximum provider stages per employer are:

1. one primary Mini direct-hypothesis request;
2. one 5.5 direct-hypothesis escalation request;
3. one residual Tavily round with a bounded initial query envelope and bounded
   domain follow-ups;
4. one late LLM adjudication only when deterministic deep evidence is ambiguous.

## Residual Tavily search

Tavily no longer runs simply because deterministic URL generation missed. It runs
only after both direct-model validation stages fail or are explicitly disabled.

The initial Tavily envelope is bounded by `--search-query-limit` (default five).
Novel model-generated queries are used first. Any remaining slots are filled with
the deterministic human-search queries. Only newly observed non-aggregator domains
may then produce the separately bounded site/domain follow-ups.

A model may return more query hypotheses than the residual envelope can execute.
Those extra hypotheses are reported as dropped by budget rather than silently
expanding provider spend.

## Symbol and numeric brands

The brand-surface layer preserves digits and verbalizes symbols:

```text
1&1 → 1and1, 1-and-1
R+V → rplusv, r-plus-v
A@B → aatb, a-at-b
```

High-value career hosts are generated before any provider call. `.org` remains in
the brand TLD set. For the original acceptance class, the bounded host set includes:

```text
https://career.1and1.org/
https://careers.1and1.org/
https://jobs.1and1.org/
```

This is a generic symbol-brand transformation and not a company-specific URL
exception.

## Human-search simulation

When residual Tavily search is required, its deterministic fallback order remains
human-readable:

1. literal brand + career wording;
2. compact/domain-safe brand + career wording;
3. official-career wording;
4. site/domain follow-up for newly observed corporate domains;
5. location-specific query only within the bounded residual envelope.

Model-generated query hypotheses may occupy the earlier residual slots because the
paired runtime benchmark proved that model reasoning adds useful search-space
information. They are still search hints only.

The adaptive reruns do not regenerate and reprobe the baseline candidate set. Only
novel search-result or hypothesis rows enter the next deterministic probe.

## Operator input

`--operator-url` remains an evidence hint and is evaluated in the deterministic
pre-provider stage. It is never accepted as truth. The query string is
canonicalized away and the URL passes the same HTTPS, source-policy, redirect,
employer-identity, career-signal and evidence gates as every provider hypothesis.

## Disable semantics

`--disable-llm` disables both direct-model stages and preserves the deterministic
→ Tavily fallback. It does not fabricate a model success.

`--disable-tavily` no longer prevents direct-model recovery. Deterministic, Mini
and 5.5 direct URL stages may complete normally; only the residual search stage is
then explicitly blocked/skipped. This is also the required private runtime
acceptance mode while the free Tavily plan is exhausted.

Missing credentials, unsupported model prices, provider failures and exceeded cost
reservations remain visible fail-closed blockers. A later bounded stage may still
recover the origin; a successful deterministic selection takes precedence over an
earlier provider failure, while a fully unresolved run preserves the blocker.

## Budget

Default per-employer ceilings:

- up to six deterministic high-value brand-host hypotheses;
- one primary `gpt-5.4-mini` hypothesis request with pessimistic reservation <= USD
  0.01;
- only on primary miss, one `gpt-5.5` hypothesis request with pessimistic
  reservation <= USD 0.05;
- only after both direct-model misses, up to five initial residual Tavily queries
  plus up to three domain follow-up queries;
- up to eighteen residual candidate rows;
- one late `gpt-5.4-mini` request only when deep evidence is eligible, with
  pessimistic reservation <= USD 0.01;
- no provider retry using an unchanged state fingerprint.

The primary, escalation and late-adjudication reservations are independent because
they serve different tasks and may be skipped separately.

## Stage compatibility

Existing reporting keeps the primary stage name:

`llm_search_hypothesis_repair`

The stronger-model stage is explicit:

`llm_search_hypothesis_escalation_repair`

Tavily and deep-evidence stage names remain unchanged. This allows historical
report consumers to remain readable while exposing the new escalation separately.

## Exit gate

The model-first correction is complete when:

1. deterministic selection skips Mini, 5.5 and Tavily;
2. Mini direct URL selection skips 5.5 and Tavily;
3. 5.5 can recover after a Mini miss or provider failure;
4. model query duplicates are removed before residual Tavily execution;
5. explicit Tavily disable still allows both direct-model stages;
6. explicit LLM disable preserves deterministic → Tavily behavior;
7. independent primary and escalation cost ceilings fail closed;
8. existing EO-002B, CAND-001, operator precedence and explicit-disable contracts
   continue to use the stable default module;
9. full repository CI, Ruff, governance and frontend checks pass;
10. private runtime acceptance with Tavily disabled proves real current candidates
    can be recovered by model-first direct hypotheses without DB/product mutation;
11. any later candidate URL persistence remains a separate CAND-001 operator
    decision.
