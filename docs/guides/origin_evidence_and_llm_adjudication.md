# Origin evidence and bounded LLM adjudication

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

The reusable provider workflow runs in this order:

1. verify the immutable database snapshot and execute the Tavily benchmark;
2. release the local PostgreSQL runtime lease;
3. inspect at most the configured number of public HTTPS candidates;
4. produce `origin-evidence-adjudication.json`;
5. optionally call the OpenAI Responses API only for deterministic manual-review
   cases and only within the configured request ceiling;
6. store both deterministic evidence and provider output in the private artifact.

The evidence step validates every redirect target, rejects local/private network
addresses, bounds response bytes and request count, and never writes to the
Pipeline database.

## LLM boundary

LLM adjudication is disabled by default. When enabled, the provider receives only
four bounded candidate records at most. The request uses a strict JSON schema and
`store=false`. The returned candidate ID must already exist in the evidence
packet. Any unknown candidate, malformed response or provider error fails closed.

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

## Recovery

`origin-evidence-adjudication-checkpoint.json` is bound to:

- the SHA-256 of the source benchmark artifact;
- ordered company keys;
- the complete evidence/LLM configuration.

Completed company results and LLM calls are restored on retry. A retry of the
same fingerprint therefore does not repeat completed adjudication calls.

## Operator activation

A live LLM run requires all of the following in the private runtime repository:

1. an `OPENAI_API_KEY` Actions secret;
2. an explicit current model ID in `llm_adjudication_model`;
3. `enable_llm_adjudication: true`;
4. an accepted `max_llm_adjudication_requests` value;
5. a caller pin to the accepted merge SHA of the public reusable workflow.

The first live run should keep the default ceiling of two LLM calls and remain a
review-only benchmark. Origin adoption is a later, separate operator-approved
slice.
