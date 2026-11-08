# Hannover TECH: Real Census Browser-Agent Benchmark (120 employers)

**No demo jobs are admissible in this benchmark.** The separate companion app
`JAP_Browser_Scout_Census_Benchmark_120.zip` runs locally on the user's WSL/Linux
host. It takes the exact accepted Hannover TECH Census JSON and produces a
reproducible, SHA-256-frozen 120-of-207 employer sample (if the original
cohort remains 207). The complete Census is **not** present in this branch.

## Measurement contract

- Population: actual REGION_HANNOVER + TECH membership pairs (not all Germany).
- Fixed sample: SHA-256(seed, company_key) ordering, first 120 distinct employers.
- Six 20-company blocks, explicit user action per block. Existing outcomes
  are individually checkpointed and never silently re-billed on resume.
- Old baseline: company_key + known true/false/unknown validated job-source status.
  Do not compare API 200 against VERIFIED_ACTIVE. Missing baseline is unknown.
- New successful source: `VERIFIED_ACTIVE` requires one real job record and
  independently supported employer/portal relationship.
- Connector readiness: definition-only Factory status is **separate** from
  successful runtime extraction/admission.
- No production writes, automatic merges, applications or scheduler changes.

## Per-employer cost and performance telemetry

The experiment runner writes `model_calls` and Responses API input/output
and cached token counts when reported. Setting the optional, private, absolute
`JAP_USAGE_LEDGER` path adds append-only `request_started` and
`response_completed` entries so completed Responses consumed before a later
error remain measurable. No OAuth token, page content or response body goes
into this ledger. Interrupted requests may still consume usage that cannot
be fully reconstructed from completed-response counters.

The local companion app records per-company:
model calls, input tokens, output tokens, cached tokens where available,
Brave search requests, browser page visits, wall seconds, status, valid jobs,
Factory definition, baseline verified, and error state. Its report includes
mean/p90 per-company usage, workload per **verified** company,
fixed-size projections for 207 and 1,000 employers, a Wilson coverage interval,
new-only/old-only matched-baseline results, and manual-audit tracking.

**ChatGPT plan/Work quota:** A Responses token count cannot be turned into
an exact percentage of the user's weekly ChatGPT app usage. The local UI must
link to ChatGPT Settings -> Usage; it must not fabricate or assume quota limits.
An app-specific SIWC limit may be hit before the overall ChatGPT plan limit.
See:
https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions
https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites

## Local operation

Use an **isolated worktree** at this experiment ref, Python 3.12+,
Playwright/Chromium, ChatGPT SIWC consent or separate API key, and
BRAVE_API_KEY for the web search provider.

1. Extract the standalone ZIP into a private working directory.
2. Activate the venv used by the experiment checkout; install its
   `requirements-browser-discovery-poc.txt` and Chromium.
3. Launch `python server.py --repo /absolute/path/to/experiment-checkout`.
4. Open `http://127.0.0.1:8765`, sign in with ChatGPT and choose an
   eligible model, then set Census file path and optional old-baseline CSV.
5. Choose **120er-Stichprobe festlegen**, inspect the frozen manifest,
   then run blocks 1 through 6 after deliberate review of quota and websites.
6. Inspect the per-employer table in the UI and the local
   `benchmark_report.html`, `benchmark_report.json` and `per_company.csv`.
7. Independently review every automatically verified source in
   `manual_audit.csv` before treating measured precision as accepted.

The standalone README also documents equivalent `benchmark.py plan`,
`run-block` and `report` commands for exact local repeatability.

## Scalability gate

Do not generalize the user's prior estimate of <=20% without the same
denominator and same verification rules. Treat a gain as credible only
when matched new-only employer wins materially exceed old-only losses,
manual verification establishes a very low false-positive rate, and
the per-verified-source cost and p90 latency are sustainable. A 120-company
sample is large enough for an engineering evaluation but not a proof of
completeness of every technology-relevant employer in the region.

**Status:** Local companion package and offline tests implemented; actual
Census snapshot, connected ChatGPT plan authorization, Brave credentials,
and host browser are not accessible in this environment. Therefore no
live success rate, true ChatGPT-plan percentage or complete comparison is
claimed until the local operator runs it.