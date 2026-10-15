# RCC capacity diagnosis and Cloud resource-saving adoption

Source review: 2026-10-15. Classic PR #1173; RCC PR #753; Cloud PR #213.
Compared RCC `0ce8230fe9c06c6d2187e5863dc28c99fee5548a`, Cloud
`29d462a2e092f3451bef98a48862c40b19e15a2e` and Classic
`67b24688b0326458e87dfa27a1684923e694a1b1` before this change.

## Ownership and remaining work

| Concern | Owner | Source state / remaining execution gate |
| --- | --- | --- |
| Pool capacity, facade eligibility, reservations, processes and runner registrations | RCC | Structured per-runner reasons implemented in PR #753; inspect actual host evidence before claiming exhaustion. |
| Legacy text-only “no free eligible General-Linux member” | RCC | Changed to RUNNER_INSPECTION_BLOCKED. CAPACITY_BLOCKED now requires structured rejection/zero-pool evidence in this classification path. |
| GitHub 403/429, quota reset, cooldown and secondary-limit backoff | RCC | Shared transport implemented; quota/auth/transport failures remain distinct from capacity. Host adoption is unproven. |
| GitHub request counts per demand, immutable source cache, runner inventory cache, status-write deduplication | RCC | Implemented centrally; Classic must reuse this authority rather than add an independent polling/cache controller. |
| Signed webhook, persistent deduplicated demand and idle controller | RCC + host ingress | Event mode source exists; external delivery and installed event-mode adoption still unproven. |
| Long-offline registration preservation | RCC | Qualified lifecycle maintainer still missing; no consumer registration workaround. |
| Consumer declaration, exact source, runtime dependencies | Classic | `pr-validation.yml` / `linux-base` matches RCC's `jap` catalog entry. Existing PR event admission needs no new scheduler. |
| Source checkout and workflow-local duplicate reads | Classic | Cloud's exact shallow materialization approach adopted for planned validation; release metadata is reused within its phase. |
| Factory proof, additive activation, ingestion and reconciliation | Classic | PR #1173 implements host entry point. Actual host DB access and job delivery remain unproven. |
| Managed productive Factory carrier | Classic + RCC admission | New Classic factory entry point is not yet a declared workflow. A consumer carrier and explicit RCC effect admission are needed for fully managed production execution; validation admission alone grants no product writes. |

The observed status for Classic's preceding head was `RCC / action qualification = pending`,
`CAPACITY_BLOCKED request=fcc51861399eb1f6`. It proves RCC saw the demand, but provides no
per-member selection reasons. It cannot distinguish occupied capacity, an old installed
controller, missing facade registrations or a masked inspection failure. Read the installed
controller SHA, exact request receipt, runner-selection diagnostics and provider budget before
changing reservations or registrations. Existing RCC read-only diagnostics own that inspection.

## What was actually adopted from Cloud

Cloud's `rcc-production-target-validation.yml` fetches an exact candidate with depth one.
Classic now does the same when RCC supplies a dynamic test plan. If the immutable policy
commit is absent, only that exact commit is fetched once. The trusted launcher still comes
from the admitted policy commit, never the candidate. Lint compares the exact policy/source
objects already present; it no longer fetches moving main in that path. The legacy no-plan
path keeps full history for its merge-base comparison. Git object transfer savings are not
claimed as reductions in REST quota.

Classic's existing-release path previously fetched the same tag once for target identity and
again for assets. One response now supplies both, saving one REST request per existing-release
inspection. The independent post-create readback remains because it verifies a new effect.
A readback failure stops for reconciliation; no automatic create retry is added. Release-list
errors already stopped before effects; that existing guard is preserved. The release inventory
is still bounded at 1,000 entries; this change does not claim zero GitHub use for publishing.

The major rate-limit work previously developed while unblocking Cloud lives in RCC, not in
Cloud business code: persistent API budget and per-demand accounting, immutable source reads,
short-lived runner inventory reuse, status projection deduplication and bounded workflow
observation. Both consumers benefit after central qualification/adoption. Copying that transport
into Classic would add another authority and would not repair allocation before workflow start.
Cloud's Azure SQL wake-up, ARM retries, Docker build and CIAM setup are not Classic equivalents
and are not imported. Classic Factory's direct host entry point performs no GitHub discovery.

## Verification boundaries

Tests execute the shallow candidate + missing exact policy + dynamic lint sequence against a
local Git origin. They verify preservation of candidate identity and policy authority without
assuming a merge-base exists. Consumer contracts retain PR events and RCC-only allocation.
Release-response reuse has a source contract test; native Windows release execution is pending.
RCC regression tests cover structured capacity, opaque legacy rejection, provider-rate precedence
and uncertain-dispatch precedence. No live rate-limit exhaustion or runner mutation was induced.

Local test counts and latest commit identities are recorded in the PRs. Merge, host adoption,
actual per-demand provider measurements and productive E2E acceptance remain separate gates.
