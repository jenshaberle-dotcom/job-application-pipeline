# Adaptive Origin Human-Search Runtime

Status: implemented for validation  
Risk: R2 bounded external-read and provider-hypothesis path  
Product role: mandatory origin discovery repair after literal baseline failure

## Trigger

The 1&1 acceptance case demonstrated a product false negative:

- deterministic baseline: `not_found`, confidence `0.200`;
- four fixed Tavily queries: `not_found`, confidence `0.650`;
- deep evidence plus late LLM: `operator_review_required`, confidence `0.756`;
- no selected or recommended URL;
- operator found `https://career.1and1.org/Access?...` through an ordinary search in
  roughly twenty seconds.

The complete technical cascade therefore ran, but its search space was too weak.
Repeating the same literal search with another provider or model would not be a
repair strategy.

## Product decision

The default URL finder becomes a finite adaptive search automaton:

```text
deterministic baseline
→ symbol-aware brand and career-host hypotheses
→ adaptive global Tavily queries
→ bounded site/domain follow-up queries
→ one early LLM search-hypothesis request
→ deterministic validation of only novel hypotheses
→ deep evidence grading
→ one late LLM evidence adjudication when eligible
→ selected URL, operator review, configuration blocker, or repair exhausted
```

The early and late LLM calls have different authority:

- early LLM: at most three new queries and three new HTTPS URL hypotheses;
- late LLM: choose, abstain, or request review among already observed evidence;
- neither LLM may persist a URL, register a connector, activate a source, write
  Bronze/Silver data, change ranking, or change scheduling.

## Anti-repetition contract

Every provider stage must add at least one of:

- a novel normalized query;
- a novel normalized URL;
- a newly observed non-aggregator domain;
- a changed discovery-state fingerprint.

Queries and URLs are normalized and stored in a per-employer ledger. Identical
inputs are never sent twice within one repair run. Discovery state is fingerprinted
from decision, confidence, and observed URLs. A repeated fingerprint records
`no_progress` and cannot trigger another provider loop.

The runtime has no unbounded loop. Maximum provider stages per employer are:

1. one bounded adaptive Tavily round, including domain follow-ups;
2. one early LLM hypothesis call plus Tavily execution of only novel queries;
3. one late LLM adjudication when deterministic evidence is ambiguous.

## Symbol and numeric brands

The brand-surface layer preserves digits and verbalizes symbols:

```text
1&1 → 1and1, 1-and-1
R+V → rplusv, r-plus-v
A@B → aatb, a-at-b
```

High-value career hosts are generated before broad path combinatorics. `.org` is
included in the brand TLD set. For the acceptance class, the first bounded host
set must contain:

```text
https://career.1and1.org/
https://careers.1and1.org/
https://jobs.1and1.org/
```

This is a generic symbol-brand transformation and not a company-specific URL
exception.

## Human-search simulation

Search order mirrors a simple human investigation:

1. global literal brand and career query;
2. compact/domain-safe brand and career query;
3. official-career wording;
4. site/domain follow-up for newly observed corporate domains;
5. location-specific query only after the corporate origin search.

The adaptive reruns do not regenerate and reprobe the baseline candidate set.
Only novel search-result or hypothesis rows enter the next deterministic probe.
This prevents request growth from masquerading as progress.

## Operator input

`--operator-url` is supported as an evidence hint. It is never accepted as truth.
The query string is canonicalized away and the URL passes the same HTTPS, source
policy, redirect, employer identity, career signal, and evidence gates as every
provider hypothesis.

## Budget

Default per-employer ceilings:

- up to five initial adaptive queries;
- up to three site/domain follow-up queries;
- up to six deterministic high-value brand-host hypotheses;
- up to eighteen adaptive candidate rows;
- one early `gpt-5.4-mini` request with pessimistic reservation <= USD 0.01;
- one late `gpt-5.4-mini` request only when evidence is eligible, with pessimistic
  reservation <= USD 0.01;
- no provider retry using an unchanged state fingerprint.

The two LLM reservations are separate because the calls serve different tasks.
The maximum default pessimistic LLM reservation is therefore USD 0.02 per employer
only when both stages are actually applicable.

## Exit gate

The slice is complete when:

1. symbol/numeric brand regression tests pass;
2. duplicate query and URL attempts are rejected;
3. repeated state is visible as no progress;
4. existing EO-002B and CAND-001 imports continue to use the stable default module;
5. full repository CI, Ruff, governance, and frontend checks pass;
6. a live 1&1 run finds or at minimum surfaces `career.1and1.org` without operator
   input;
7. the operator URL remains evidence-only until CAND-001 explicit persistence.
