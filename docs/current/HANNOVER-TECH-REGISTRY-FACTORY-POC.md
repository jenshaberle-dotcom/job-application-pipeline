# Hannover TECH – Registry → Verified Portal → Connector Factory (isolated PoC)

Branch: poc/hannover-tech-registry-factory-e2e-20261106

## Objective and authority boundary

Measure three separate rates over the **same** frozen REGION_HANNOVER / TECH company population:

1. Company and portal coverage from two external registers.
2. Verified portal coverage and the explicitly enumerated *long tail*.
3. Conversion of **verified** employer portals into the existing declarative JAP
   Connector Factory, with a bounded real/replayed public-feed extraction check.

**Do not report a percentage for all Hannover TECH businesses.** The denominator
is only the supplied Census cohort. The accepted 2026-10-05 Census was documented
with 211 identities / 207 TECH, but its actual immutable records must be supplied.
The examples directory contains fictional data and is not a substitute.

This branch does **not** activate sources, register production connectors, modify
PostgreSQL, schedule work, touch RCC, dispatch workflows or change JAP Runtime.
Factory recipes in report.json are candidates, not live runtime admission.

## 1. Separate local worktree (safe with an actively edited working tree)

Run in the existing JAP Classic checkout:

    git fetch origin poc/hannover-tech-registry-factory-e2e-20261106
    git worktree add --detach ../jap-hannover-tech-poc \
      origin/poc/hannover-tech-registry-factory-e2e-20261106
    cd ../jap-hannover-tech-poc
    python3.12 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt
    python -m pip install pytest

This is a *second* checkout: it leaves uncommitted work in your original working
tree untouched. It does not automatically bring local unpushed development into
the PoC. Git worktrees share the repository's object store; for an independent
backup also push the local development branch separately.

## 2. Fully offline, repeatable E2E demonstration

Run from the repository root:

    python -m pytest -q tests/test_hannover_tech_registry_poc.py

    python -m scripts.run_hannover_tech_registry_poc \
      --census examples/hannover-tech-registry-poc/census.json \
      --openjobs examples/hannover-tech-registry-poc/openjobs.json \
      --boards examples/hannover-tech-registry-poc/boards.json \
      --replay examples/hannover-tech-registry-poc/replay.json \
      --output runs/hannover-tech-poc-demo

The fabricated Alpha Analytics fixture demonstrates:

- Identity matching across the Census and an independent company dataset.
- Link on the claimed official company website to an exact Greenhouse tenant.
- A recorded Greenhouse public jobs API response, including job content.
- Calling the **existing** JAP aggressive_factory / catalog for recipe creation.
- Calling the **existing** connector_extraction runtime for one job metadata record.
- Result clearly marked OFFLINE_FIXTURE, not a real 2026 job observation.

Fictional Beta Robotics has a matching register record without an ATS board;
Gamma Machines is unmatched. A Berlin-only company is excluded.

Expected sample metrics: 3 Hannover TECH rows, 2 register matches,
1 registry portal candidate, 1 verified portal, 1 inactive Factory recipe and 1 extracted job in the
synthetic replay. The sample does **not** establish live performance.

## 3. Real Hannover TECH coverage measurement

### Prepare immutable, attributable inputs

Use the actual accepted or freshly qualified Census JSON export containing
the **candidates** array, company_key, company_name, TECH and region membership
(either scope_memberships pairs or geographies / cohorts), and employer websites
(in the actual multi-region Census, the field is a **websites array**). Multiple
ambiguous corporate domains deliberately remain unresolved.
Do not create names from domain fragments. Do not use the rejected October
421-candidate parser artifact. Do not replace missing source records with a
manual list and label them "Census".

Obtain the public registers and store copies with stable SHA-256 digests:

    mkdir -p runs/hannover-tech-registry-poc/inputs

    curl -fLsS --retry 2 \
      https://raw.githubusercontent.com/outscal/OpenJobs/main/data/companies_v2.json \
      -o runs/hannover-tech-registry-poc/inputs/openjobs.json

    curl -fLsS --retry 2 \
      https://kalebconfer-sys.github.io/job-board-directory/job-board-directory.json \
      -o runs/hannover-tech-registry-poc/inputs/boards.json

    sha256sum runs/hannover-tech-registry-poc/inputs/*.json

Sources: https://github.com/outscal/OpenJobs (MIT; dataset is point-in-time)
and https://kalebconfer-sys.github.io/job-board-directory/ .
Respect source licenses, rate limits and jobsite terms. Neither directory
supplies an automatic ownership guarantee. A matched ATS name alone is not proof.

### First pass: registry gap without HTTP probes or credentials

    python -m scripts.run_hannover_tech_registry_poc \
      --census /ABSOLUTE/PATH/TO/ACTUAL_HANNOVER_CENSUS.json \
      --openjobs runs/hannover-tech-registry-poc/inputs/openjobs.json \
      --boards runs/hannover-tech-registry-poc/inputs/boards.json \
      --output runs/hannover-tech-registry-poc/registry-only

This gives (a) matched company names, (b) register-suggested portal addresses,
(c) no register coverage, (d) suggested candidate list per company. Portal
ownership and Factory extraction are deliberately **not yet measured**; the
portal gap percentage appears as n/a rather than zero or 100 percent.

### Second pass: provenance check + Connector Factory smoke

Start with a limited live probe:

    python -m scripts.run_hannover_tech_registry_poc \
      --census /ABSOLUTE/PATH/TO/ACTUAL_HANNOVER_CENSUS.json \
      --openjobs runs/hannover-tech-registry-poc/inputs/openjobs.json \
      --boards runs/hannover-tech-registry-poc/inputs/boards.json \
      --live --limit 20 \
      --output runs/hannover-tech-registry-poc/live-20

A limited run is always marked **partial** and must not be used as the
full-cohort coverage rate. The live mode requests public HTTPS pages only,
with bounded timeouts/response size and redirect validation. Use this only
against approved public sources; it is not a production-grade crawling service.

For a company site to be treated as reliable, this baseline requires either:
- Company name + independently matching OpenJobs website domain + company
  homepage title/H1 evidence, or
- Explicitly reviewed corporate website, supplied in approved-websites JSON.

Example of the latter (use your actual Census company keys and reviewed domains):

    {
      "reviewed-company-key": "https://verified-employer.example"
    }

Pass the path with --approved-websites. The example domain above is illustrative;
do not copy it into a real approval file. Manual website approval certifies
the **corporate website**, not an ATS board; an actual outbound career link
must still be found. HTML-only pages without a linked job source remain open.

When a verified exact Greenhouse/Lever job board yields parseable public records,
the PoC calls JAP's **existing** catalog, aggressive_factory and connector_extraction.
It emits an inactive connector recipe and a bounded extraction smoke result.
No false PASS is emitted for empty/blocked/unsupported sources.

### Optional third pass: targeted search for the long tail

    export BRAVE_API_KEY='YOUR_KEY_FROM_SECURE_ENV'
    python -m scripts.run_hannover_tech_registry_poc \
      --census /ABSOLUTE/PATH/TO/ACTUAL_HANNOVER_CENSUS.json \
      --openjobs runs/hannover-tech-registry-poc/inputs/openjobs.json \
      --boards runs/hannover-tech-registry-poc/inputs/boards.json \
      --live --brave-search --limit 20 \
      --output runs/hannover-tech-registry-poc/search-20

Uses Brave Web Search for up to ten organic candidate URLs per company, plus
up to two pages from the exact corporate website. Search results are
**discovery-only**; no third-party search hit can authorize an ATS source.
Quota and public API costs apply. Do not commit API keys or exported real
candidate/job data. For larger runs, use a deliberate search budget.

## Report interpretation

Outputs are always local under --output:

- report.json: every company, candidates, provenance, selected actual
  company-site links, Factory decisions and up to 3 extracted job examples.
- report.md: rollup rates and first 30 unresolved company names.
- companies.csv: one row per employer for diff/quality review.
- long_tail.csv: unresolved or not-yet-verified sources.

Distinct denominators and gaps:

- registry_company_match: exact normalized company identity or exact website host.
- registry_portal_candidate: company has an ATS URL in matched registers.
- verified_portal: confirmed corporate identity + observed link from that site
  to the exact career board tenant; search ranking alone never suffices.
- verified_registry_portal: confirmed portal with a corresponding register board.
- delta_verified_without_registry_portal: additional official portals not in a
  matched register; this is the discovery gain after register lookup.
- long_tail_registry_gap_closed: no register company match, but a source was
  subsequently verified via official website evidence.
- factory_recipe_built: definition proof produced using JAP's actual catalog.
- factory_extracted: definition followed by a successful extraction smoke test
  using JAP's actual interpreter.
- long_tail_registry_gap: not found in either register.
- long_tail_portal_gap: no verified source **after evidence inspection**.
- long_tail_factory_gap: source verified, but no successful Factory extraction.

A source can be valid with zero open jobs. The current Factory catalog requires
nonempty job content to fingerprint some provider families, so an empty but
verified board is reported as source-verified / factory-gap, not "invalid".
Workday, Personio and generic HTML/JSON-LD need additional provider-specific
or evidence-qualified extraction support in this focused PoC; do not claim
connector success for them. True production admission requires a separate,
authorized runtime qualification with independently observed golden responses.

## Evaluation and next iteration

Before changing the architecture, freeze the full Census snapshot, run registry
coverage once, then compare live verified evidence on the same cohort.
Audit at least 20 positive and 20 negative/unresolved cases manually.
Do not tune thresholds on the evaluation set. Keep source timestamps/digests
and rejected URL reasons for reproducibility.

Only then design long-tail interventions by observed blocker class:
missing company identity, register absence, absent official links, redirect/JS
rendering, provider not supported, or extraction contract missing.

**Security note:** The PoC makes bounded HTTPS requests and rejects private
DNS answers, but does not offer a full browser sandbox, DNS-rebinding-resistant
transport, robots/ToS policy engine or secret-management facility. Treat it as
operator-invoked research code, never as an autonomous broad crawler.


### Verification status of this branch

The commit includes a deterministic offline pytest suite and replay fixture.
It was authored remotely through GitHub; the author's environment had no local
checkout or live database access to execute the suite or obtain the real Census
artifact. Run the pytest command above before treating the demo as validated;
then run with the real Census to obtain actual Hannover coverage figures.
