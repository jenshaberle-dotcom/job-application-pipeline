# Operator Origin Attestation

## Purpose

This guide describes the read-only fallback for an exact employer career URL that is publicly reviewable by an operator but not fetchable by the approved non-browser collector.

The command does **not** open the website. It only processes evidence that the operator already saved locally through ordinary browser use.

## Safety boundary

Do not use this path to defeat access controls. Do not provide challenge pages, CAPTCHA output, copied cookies, authenticated sessions, challenge tokens, stealth-browser output, or material obtained through fingerprint or proxy evasion.

When ordinary access is blocked, the collector remains `blocked_by_access_control`. Operator attestation can establish origin truth only; it cannot make collection ready or activate a source.

The generated JSON is marked:

```text
review_output_only_not_pipeline_input=true
source_activation_allowed=false
provider_requests=0
pipeline_mutation=false
```

## Preparing evidence

Using an ordinary browser session, save a UTF-8 text or HTML representation of the public page content. The file must contain:

- the exact distinctive employer entity, not only its parent brand;
- at least one career or job signal;
- no challenge-page text such as `Just a moment`, CAPTCHA, or `Verify you are human`.

A screenshot may be supplied as additional hashed evidence. The screenshot bytes are never embedded in the JSON artifact.

## Example command

```bash
python -m scripts.run_origin_operator_attestation \
  --company-key e_on_digital_technology \
  --operator-url "https://www.eon.com/de/ueber-uns/karriere/unsere-gesellschaften/digital-technology.html" \
  --reviewer-identity "operator:jens" \
  --approval-token "<unique non-secret approval phrase>" \
  --page-title "E.ON Digital Technology Careers" \
  --entity-token digital \
  --entity-token technology \
  --career-signal karriere \
  --career-signal jobs \
  --content-file "$HOME/evidence/eon-digital-technology.html" \
  --screenshot-file "$HOME/evidence/eon-digital-technology.png" \
  --observed-at "2026-08-04T12:00:00+02:00" \
  --expires-at "2026-09-03T12:00:00+02:00" \
  --output "$HOME/product_v1_runtime_artifacts/eon_operator_attestation.json"
```

The raw approval phrase is not written to the artifact. Only its SHA-256 digest is retained.

## Expected decision

Without separate collector-capability evidence, a valid artifact replays as:

```text
origin_truth_state=verified
collection_state=unknown
decision=origin_verified_collection_unknown
source_activation_allowed=false
```

Combining it later with the existing read-only 403 collector evidence may yield `origin_verified_collection_blocked`. That combination belongs to a separate, reviewed slice.

## Rejection cases

The writer fails closed when:

- the URL is not HTTPS;
- the content file is absent, empty, too large, or not UTF-8;
- distinctive entity tokens are missing;
- every declared career signal is missing;
- challenge-page markers are present;
- timestamps are invalid or expiry is not later than observation;
- provenance or approval fields are missing;
- the output path already exists.

Existing evidence is never overwritten.
