# F4B current-cohort baseline — 2026-09-15

Status: READ-ONLY EVIDENCE / F4B ACCEPTANCE BLOCKED

Authority: `main@35224c9b8351a3a260ba5d5e51236d61bb7ed8f5` for the accepted campaign Re-Entry; candidate reconciliation code at `agent/f4b-readonly-cohort@74c9f5e0b466cc8bc9027640d1689c7725c7eb27`. The latter is a Draft PR (#888), not production ranking authority.

## Exact-head evidence

- Warm Product reconciliation run [34993687905](https://github.com/jenshaberle-dotcom/job-application-pipeline/actions/runs/34993687905): successful read-only execution and short-lived per-job artifact; no provider calls or DB writes.
- Warm F4A Origin-to-Silver preflight run [34993150670](https://github.com/jenshaberle-dotcom/job-application-pipeline/actions/runs/34993150670): 70 proposals, 70 operator rows, complete reachable coverage, zero projection loss or violations.
- Candidate-head Pipeline CI run [34993717079](https://github.com/jenshaberle-dotcom/job-application-pipeline/actions/runs/34993717079): Full Suite, Ruff, governance/CI contracts and React build passed. Re-Entry identity run [34993716742](https://github.com/jenshaberle-dotcom/job-application-pipeline/actions/runs/34993716742) passed.

## Current Product funnel

The Product payload has **71** `active_confirmed` Silver identities, all with `origin_validation_status=validated`. All 70 F4A preflight Silver proposals overlap this set. The extra Product identity is Silver `174` (`personio:1komma5grad`), currently active and Origin-validated, with unknown Profile Fit and hard-filter evidence required. Thus the 70/71 counts have different cohort scopes; they are not evidence of a missing F4A projection.

| Gate or state | Current count |
|---|---:|
| Profile Fit `unknown` / insufficient evidence | 69 |
| Profile Fit `failed` / conclusive negative hard requirement | 2 |
| Product hard-filter evidence required | 69 |
| Product blocked hard filter | 2 |
| Current Top-5 members | 0 |
| Complete current Affinity score components | 0 |
| Evidence-backed numeric Fit scores | 0 |
| Read-only arithmetic/geometric combined candidates | 0 |

All 71 rows report `approved_candidate_geography_preference_missing_or_ambiguous` and `exact_current_candidate_fact_capability_review_missing`. Seniority consequently requires current capability evidence on all 71. Hard-requirement evidence is unknown on 69; two have deterministic negatives. The local Product DB has seven active passed capability reviews, but only one is exact-bound to its assessment and that job is inactive. Six active-current reviews have revision/decision binding drift after upstream assessment changes; their earlier `passed` verdicts cannot be reused as exact-current authority. The approved Candidate Fact profile and seven approved professional/education/portfolio/training facts exist, but no approved `profile-fit.*` geography preference dimension is projected.

The F4A exact-Origin sidecar plan explains much of the hard-evidence gap across its 70-job scope. `employment_type` is `source_absent` on 65, `required_languages` on 45, `weekly_hours` on 46, and `requirements_seniority` on 64; skills are `source_absent` on 17. Four Origin detail reads are unavailable (Silver IDs `434`, `491`, `543`, `544`). The plan has no `extractor_gap` among reachable jobs. These are absence/unavailability states, not a license to infer positive requirements from title, source family or employer. The additional Product job `174` is outside this F4A proposal scope and remains explicitly unknown.

The current runtime ranking policy reports `minimum_quality_score=60` under `product-v1-2026-09-03`. The canonical `PD-051` register, current Re-Entry and migration 078 retain **70/100** until separately changed. No repository decision superseding `PD-051` was found in this audit. This is an authority contradiction, so the runtime 60 threshold cannot authorize F4B combined-score promotion. The reconciliation records the mismatch; it does not mutate the policy.

## Hannover Re residual #884

Silver `599`, `generic_origin:hannover_ruck`: F4A exact-Origin sidecar hash `13b5f039036b96e2e50c2162a754255f03cee2aaf01818607b019501a01ab571` is converged (`would_change=false`). The [authoritative vacancy](https://jobs.hannover-re.com/job/Hannover-Working-Student-Taxation-and-Tax-Reporting-Economics/1363418455) states **20 hours per week**, with exact bounded span `2354..2371`. The approved hard-filter policy requires 35–40 weekly hours. Product therefore reports `hard_filter_failed:weekly_hours` and `profile_fit.failed:hard_requirements`. This is an evidence-backed conclusive negative under the current policy; high Affinity cannot override it.

Silver `600`, same source family: converged sidecar hash `03a8f12d298146aa50e88837cf4e207527b6afd89962917597cea88a51269996` retains **fixed-term role** at exact bounded span `954..969` in the [authoritative vacancy](https://jobs.hannover-re.com/job/Sydney-Senior-Claims-Assessor-NSW-2000/1364581555). The approved hard-filter policy requires permanent employment. Product reports `hard_filter_failed:employment` and `profile_fit.failed:hard_requirements`. This is also an evidence-backed conclusive negative. Both cases use generic vacancy evidence and the existing policy, with no employer-specific exception. Other Fit factors remain unknown; the conclusive negative is sufficient to exclude each job without manufacturing a numeric Fit value.

## Next gate

Keep `PD-052` production ranking unchanged. The next F4B work is a provider-free, exact-revision review packet for the current capability and hard-filter evidence gaps, then explicit operator decisions on Candidate Fact fit reviews, actual geography/work-model boundaries, numeric Fit rubric and the `PD-051` runtime-policy contradiction. Only after current evidence is sufficient can the `60% Fit + 40% Affinity` arithmetic and stronger low-component-penalty candidates be compared on real jobs. Neither formula is approved ranking authority. The full frozen flow still requires exact-head CI/Product proof, merge, immutable release, automatic local deploy and installed operator acceptance before F4C.

## Paid-provider budget ledger

Campaign cap for additional paid API/provider tokens: **USD 10.00**. Paid calls through this checkpoint: **0**. Incremental paid spend: **USD 0.00**. Remaining paid-provider budget: **USD 10.00**. Local DB reads, repository work and GitHub CI are free under the campaign accounting rule. A future paid call must record provider, model, billed units, price evidence, USD debit and remaining balance before another call; uncertain billing fails closed.
