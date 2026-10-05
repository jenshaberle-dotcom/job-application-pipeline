# Multi-Region Connector Factory Lab

JAP Classic is the development, benchmark and experiment environment for the JAP Cloud
Connector Factory, not a product to preserve. Tracking: #1166, #1167, #1168, #1169.
Quality > cost > time.

## One execution path

Public Company Discovery → Multi-Region Census → Career/Origin Evidence → Fingerprinting
→ aggressive Connector Factory → Generic Extraction → Qualification → Evaluation → labelled ML corpus.

`connector_factory.py` and `connector_extraction.py` remain the sole Factory core and recipe
runtime; `aggressive_factory.py` owns advancement. Directory profile URLs are lineage, not
employer domains or execution authority. Market sensors are not employer connectors.
No per-employer parser, production activation or alternative scheduling authority is introduced.
TECH covers REGION_HANNOVER, WOLFSBURG, INGOLSTADT, STUTTGART_REGION, BERLIN and MUNICH.
SOCIAL covers Hannover city and Region Hannover only. `scope_memberships` preserves actual
observed geography/cohort pairs without a false cross product.

## Real corrected Census: 2026-10-05

The operator executed the already prepared corrected flight at Classic source
`cf417719b9b239e157d1dc387c0ea291c78f9e9d`, using existing RCC source
`4a04c21e8feec202e64a2aaabf1d578fdb49022e` and the original corrected authority
`RCC-OPERATOR-CENSUS-1169-CORRECTED-01`. Upload probe `37284340115` and Census
`37284528867` passed. The Census job `111680162634` passed all steps, including upload
and workspace cleanup. Operator evidence reports runtime reuse and final
`OFFLINE_DISABLED_EXACT_ONLY`. Reservations were respected, not deleted.

Downloaded artifact `11333892082` (32,319 bytes) has verified ZIP SHA-256
`dd20b42150aaa1a6226ad70d1ec21d96c9799fc70bdcae486e304ac4d840b97e`.
The population digest was independently recomputed as
`233cfec179f156d04d7001e38fb8b6d0e6ca6cd8873f0a8f2bab25a698b8eb99`.
All four retained source-snapshot digests match their bytes.

Hannover produced 213 directory rows on 54 pages, deduplicated into 211 candidate
identities by the existing domain/name policy. Of those, 207 carry TECH and nine carry
SOCIAL; five carry both. All 211 have directory-profile evidence and 210 have a supplied
employer website. Known `Homepage`/URL-as-name failures and cross-company discovery-ID
collisions are absent. This accepts the parser repair, not independent verification of
all current legal entities, addresses, technical sectors, websites or vacancies.
The domain identity rule merges two pairs of group/company entries; 211 is not a legal
entity census. SOCIAL is the source's broad health/social category, not nine verified
social-work employers. Region-wide completeness is not proven by this one directory.

The aggregate artifact still contains one unaccepted Ingolstadt event/opportunity link:
`Startup Opportunities: Dual-Use Innovation`. Its accepted-company contribution is zero.
Berlin/Wolfsburg failed with only `CalledProcessError` retained. Munich/Stuttgart returned
zero parsed records. None of these observations proves an empty market. The stored
`factory_run_recommended=true` is structural advice, not semantic clearance of that event.
TECH thresholds are unmet in every region; `ml_scale_ready=false` remains correct.

The first flight `37279612056` at `8fcddf12e2200521df566ddefeec923fea092c2c` remains
immutable rejected-parser evidence (artifact `11331628069`, 421 corrupted candidates).
Its consumed authority `RCC-OPERATOR-CENSUS-5989799201` stays consumed. Do not reset
or replay either flight, overwrite an artifact or manufacture employer names from domains.

## Source repairs and remaining gates

The existing source orchestrator now retains bounded failure categories and numeric HTTP
statuses from terminal child exceptions, never raw stderr, credentials, response bodies
or private paths. Empty parsing is `NO_RECORDS_PARSED`, not `ZERO_COMPANIES`. A source's
explicit `complete=false` propagates to its outcome. Existing source-isolation and stale
snapshot rejection remain; there is no automatic retry.

The known brigk event path is excluded in its existing source configuration. The public
site lists that link under events; this exclusion does not establish a replacement
Ingolstadt company directory. Source: https://www.brigk.digital/ (inspected 2026-10-05).

The Munich portal now redirects `/startups/` to
https://www.munich-startup.de/en/startups-and-ecosystem and publishes individual profiles
below that namespace. The old WordPress `paging` traversal is removed. The adapter reads
actual same-origin profile links and each profile's H1, not the whole card description
or a name guessed from its slug. At most 24 details are read, preserving good rows when
individual details fail. The first visible page is explicitly incomplete:
`pagination_status=UNQUALIFIED_LOAD_MORE`, `complete=false`. Full Load-more/API pagination
still needs a verified public interface; no arbitrary page parameter or total-count
completeness is invented. Portal metadata is research evidence, not an RCC census result.
The source's existing TECH cohort remains a broad startup benchmark; individual technical
classification and exact city/region fit still require evidence.

Stuttgart currently exposes an interactive technology map at
https://www.region-stuttgart.de/type/unternehmen/ rather than a proven static company-link
list. Its data interface remains unqualified. Berlin/Wolfsburg failure causes need the
new safe diagnostics or a verified replacement directory, not another blind batch.
Additional SOCIAL directories must establish real organization and location evidence.

Next: qualify these code changes through the existing RCC full-plan PR carrier. Then admit
only purposeful source-repair or Origin/Factory work; the successful Hannover result is
reusable evidence, not a reason to refetch all 54 pages on every diagnostic iteration.
No newly repaired source flight, Factory extraction or additional company count is claimed.

## RCC and corpus truth

`connector-factory-hannover-census.yml` maps to `linux-base`; only RCC owns allocation,
profile materialization, reservation and exact assignment. The automatic PR carrier remains
validation-only. A green PR or mapped demand does not authorize public discovery, SQL,
Azure, provider calls or production source activation. Workchat dynamic testing and merge
reuse were proven with #1168; CC-driven capacity scaling is a separate acceptance gate.

`evaluate_connector_factory_corpus.py` still requires acquired origin evidence and preserves
the complete admitted population. `materialize_connector_ml_corpus.py` enforces one-to-one
population and digest binding. Definition-only `qualified_inactive`/`recipe_ready` labels
are `RUNTIME_GAP`; SUCCESS/ZERO_JOB_VALID_SOURCE need verified origin, admitted runtime,
passing qualification and complete extraction with measured job count. The corrected
Hannover directory observations are not yet working connectors or an ML-ready corpus.
