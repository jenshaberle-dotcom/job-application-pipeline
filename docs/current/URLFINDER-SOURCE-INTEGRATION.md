# URL-Finder source integration: 2026-11-07

Status: tested local integration candidate, not pushed or deployed. User acceptance pending.

## Exact inputs

- JAP main: `819e0df0a9ea8c92866dfdb2ac4f17acdee0d10f`.
- Branch `poc/hannover-tech-registry-factory-e2e-20261106`: `5b43ad4c3ab6939626607e24bc1a151f8b17ecc2`.
- Merge base equals the observed main; branch is 52 commits ahead, none behind.
- The archive comparison contains 16 added files and one changed file; no deletions.
- Local URL-Finder rules: operator source packages 0.12.19–0.12.21.
- RCC remote source capture failed with anonymous HTTP 404; current RCC source and access remain unverified.

## Decisions

| Approach | Decision | Reason / implementation |
|---|---|---|
| Frozen cohorts and separate register/portal/extraction rates | Retain | PoC does not claim a complete regional census or production admission. |
| Existing compiler and extraction interpreter | Retain | `hannover_tech_registry_poc.py` uses the actual repository factory. |
| Metadata, iframe and literal widget routes | Combine | Shared `portal_discovery.discovery_candidate` feeds the PoC candidate selection. |
| Personio tenant identity | Repair | Subdomain root is a tenant, not a vendor root; exact tenant comparison. |
| Aliases during cohort expansion | Repair | Ambiguous aliases stop identity reconciliation instead of selecting the first employer. |
| Local five-family field evidence | Port | Fourteen modules under `src/connectors/portal_discovery/`; original compiler reused. |
| XML feed capability | Port | Add the existing local `XML_FEED` strategy label; no runtime activation. |
| TECH target roles / inactive SQL experiment | Retain as experiment | Does not change Christina's profile or activate search terms. |
| `local_jap_guard.py` and its documentation/tests | Defer | Targets Classic + job-pipeline-runtime, creates orphan backup branches and does not cover this RCC source integration; not our main publication path. |
| Brave live mode / prototype transport | Not admitted | Optional prototype remains explicit; no credentials or provider calls in this review. Requires RCC transport/budget qualification before autonomous use. |

The prototype still limits the initial cohort to Hannover TECH. The local field
modules work with the frozen mixed TECH/SOCIAL plan. These are distinct entry
points, not a claim that a single production scheduler now supports both.

## Verification and remaining work

85 tests and 12 subtests pass offline: remote PoC/profile/SQL-staging tests,
ported field contracts and new regression cases. Test dependencies were reused
from the local package cache, without installation or download. No network,
services, production databases or GUI changes occurred.

The original SQL test failed because it split lowercased SQL using an uppercase
needle; only that test assertion was corrected. No SQL was executed.

Stored 0.12.21 evidence reproduces exactly after the module move: all 1025 retained
response bodies pass their hashes, with zero missing responses or source calls. Its field
result is 24 portal candidates / 19 candidate recipes with job samples across
260 selected records (290 targets), from a frozen total of 3380 source records.
No new live success is attributed to this integration. Personal acceptance,
production registration, daily scheduling and the 90% target remain open.

The source backup scope is explicitly URL-Finder/ATS changes 0.12.19–0.12.21,
not the entire historical set of RCC, desktop and daily-delivery packages.
Those remaining differences need a separate source/deployment inventory.

The next publication must use real Git history, recheck main and branch SHAs,
apply the reviewed file-level result, run tests and obey branch protection.
Never force-push, replace a live checkout, or publish raw response archives,
credentials or private application documents. Verify remote main and exact file
contents before reporting GitHub backup complete. Source publication does not
activate a service or imply user acceptance.
