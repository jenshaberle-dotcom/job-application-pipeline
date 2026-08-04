# Browser-Protected Origin Replay

## Purpose

This guide closes the evidence gap between an operator-verified employer origin and an approved collector that remains blocked by HTTP 403.

The replay does not fetch the website. It combines two already existing local JSON artifacts:

1. an `origin_operator_attestation` artifact proving the exact employer/URL relationship; and
2. an earlier origin-repair artifact containing exact-URL HTTP 403 evidence from the approved non-browser collector.

The honest result is:

```text
origin_truth_state=verified
collection_state=blocked_by_access_control
decision=origin_verified_collection_blocked
source_activation_allowed=false
```

## Safety boundary

The replay performs no network request and does not try the URL again. It does not change headers, cookies, HTTP methods, sessions, fingerprints, proxies, CAPTCHA handling, challenge tokens, or browser behavior.

HTTP 403 remains blocked evidence. The replay cannot mark the collector ready and cannot activate a source, create a connector, write Bronze/Silver data, change rankings, mutate the database, or alter schedules.

The output is marked:

```text
review_output_only_not_pipeline_input=true
provider_requests=0
pipeline_mutation=false
source_activation_allowed=false
```

## Required files

- the operator attestation JSON produced by `scripts.run_origin_operator_attestation`;
- the prior `origin_url_default_repair_*.json` artifact that contains the exact E.ON URL, HTTP 403, `reachable=false`, and challenge/access-control evidence.

The collector timestamp is derived from the standard artifact filename when possible. It can be supplied explicitly when the filename has no timestamp.

## Example

```bash
REPLAY_AT="$(date --iso-8601=seconds)"
OUTPUT="$HOME/product_v1_runtime_artifacts/eon_blocked_origin_replay_$(date +%Y%m%dT%H%M%S).json"

python -m scripts.run_browser_protected_origin_replay \
  --company-key e_on_digital_technology \
  --operator-url "https://www.eon.com/de/ueber-uns/karriere/unsere-gesellschaften/digital-technology.html" \
  --origin-artifact "$HOME/product_v1_runtime_artifacts/eon_operator_attestation_20260804T132728.json" \
  --collector-artifact "$HOME/product_v1_runtime_artifacts/origin_url_default_repair_20260804T095656995956Z.json" \
  --replay-at "$REPLAY_AT" \
  --output "$OUTPUT"
```

## Fail-closed cases

The command rejects:

- a company or exact URL mismatch;
- a generic 403 without challenge/access-control evidence;
- a 403 record that says the URL was reachable;
- collector evidence containing provider requests;
- artifacts reporting pipeline mutation or source activation;
- expired or malformed evidence;
- an output path that already exists.

The recursive collector scan avoids depending on one fragile JSON nesting path, but the exact URL, HTTP 403, `reachable=false`, and challenge evidence must still occur in the same bounded observation subtree.
