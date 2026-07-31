# Origin evidence, model benchmark, and bounded LLM adjudication

## Purpose

The origin-provider benchmark discovers plausible first-party employer URLs. The
post-processing step proves as much as possible deterministically before an LLM
is allowed to comment on unresolved ambiguity.

The implementation keeps four independent evidence dimensions:

- entity fidelity: legal entity, brand, parent/group, related or ambiguous;
- source grade: ATS/job listing, company listing, career landing, job detail,
  corporate page, aggregator or social profile;
- job inventory: concrete jobs proven, explicitly empty, unknown, not job-bearing
  or fetch failed;
- target signals: bounded evidence from job-link labels and URLs for the current
  profile/location.

No single saturated score replaces these dimensions. Ranking confidence is
bounded below `1.0` and includes the winner-versus-runner-up margin.

## Runtime contract

The reusable evidence workflow runs in this order:

1. verify the immutable database snapshot and execute the Tavily benchmark;
2. release the local PostgreSQL runtime lease;
3. inspect at most the configured number of public HTTPS candidates;
4. produce `origin-evidence-adjudication.json`;
5. optionally call the OpenAI Responses API only within an explicit request and
   cost ceiling;
6. store deterministic evidence and provider review signals in private artifacts.

The evidence step validates every redirect target, rejects local/private network
addresses, bounds response bytes and request count, and never writes to the
Pipeline database.

## LLM boundary

LLM adjudication is disabled by default. When enabled, the provider receives only
four bounded candidate records at most. The request uses a strict JSON schema,
low reasoning effort, low output verbosity, and `store=false`. The returned
candidate ID must already exist in the evidence packet. Any unknown candidate,
malformed response, or provider error fails closed.

The provider may:

- confirm that the deterministic conflict is real;
- recommend one existing candidate for operator review;
- require manual review;
- abstain.

The provider may not:

- introduce a new URL;
- assert unobserved jobs or entity relationships;
- overwrite deterministic measurements;
- activate or persist an origin;
- bypass operator review.

## Fixed three-model mini-campaign

`reusable-origin-llm-model-campaign.yml` first produces one immutable evidence
artifact and then runs these explicit model IDs on each matched case:

1. `gpt-5.4-mini`;
2. `gpt-5.6-terra`;
3. `gpt-5.5`.

The model ID is the only intentional request difference. For every company, the
campaign verifies identical hashes for:

- the evidence packet;
- system instructions;
- strict JSON schema;
- reasoning effort;
- output-token ceiling;
- `store=false` and low-verbosity settings.

The fixed six-case benchmark contract covers E.ON Grid Solutions, Hannover Rück,
msg systems, Materna, x1F, and Genoverband. It records per-case quality, critical
failures, latency, usage-derived estimated cost, and pairwise escalation results.

The benchmark has these hard defaults:

- six cases;
- three models;
- no more than 18 provider calls;
- 600 output tokens per call;
- pessimistic input reservation of 5,000 tokens per call;
- pessimistic campaign ceiling of `$0.50`.

The price table is a dated implementation snapshot and must be revalidated before
a later campaign if provider pricing changes. Actual artifacts retain provider
usage and the usage-derived estimated cost for audit.

## Model selection rule

The campaign does not select the largest model by assumption. It recommends the
cheapest model that:

- has no critical benchmark failure;
- reaches at least `0.80` mean quality;
- remains within `0.05` of the best observed model quality.

If several models meet that bar, the cheaper observed route wins.

## Escalation path

A primary result can request one stronger second attempt only when it:

- fails closed;
- abstains;
- conflicts with a strong deterministic winner;
- attempts to clear a deterministic manual-review requirement; or
- leaves a high-evidence semantic ambiguity unresolved.

The benchmark recommends an escalation model only when it demonstrably corrects
at least one primary-model miss, reaches a safe score on that case, and produces
at least `0.10` mean score lift across triggered cases. Model size alone is not
accepted as evidence of value.

The live path performs at most one primary and one escalation call per company.
If both providers disagree, the result is always
`provider_disagreement_manual_review_required`. Provider consensus still remains
an operator-review signal and never becomes mutation truth.

The default live envelope is:

- at most two primary calls;
- at most two escalation calls;
- pessimistic total ceiling of `$0.15`.

## Recovery

The deterministic checkpoint is bound to the source artifact and the complete
runtime configuration. The model-campaign checkpoint additionally binds:

- the SHA-256 of the immutable evidence artifact;
- the SHA-256 of the benchmark expectation contract;
- ordered company keys;
- ordered model IDs;
- token, reasoning, request, timeout, and cost ceilings.

Completed model calls are restored on retry. A retry of the same campaign cannot
silently change models or repeat completed provider work.

## Operator activation

A live model benchmark requires all of the following in the private runtime
repository:

1. an `OPENAI_API_KEY` Actions secret;
2. a caller pin to the accepted merge SHA of the public reusable workflow;
3. `campaign_mode: benchmark`;
4. the exact model order `gpt-5.4-mini,gpt-5.6-terra,gpt-5.5`;
5. explicit acceptance of the 18-call and `$0.50` pessimistic ceiling.

After reviewing the benchmark artifact, the operator may approve a proven route
by changing `campaign_mode` to `adjudicate` and setting the recommended primary
and escalation IDs. If the campaign does not prove escalation value, the
production path must not add an escalation call merely because a larger model is
available.

Origin adoption remains a later, separate operator-approved slice.
