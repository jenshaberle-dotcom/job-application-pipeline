# Job Application Pipeline

Status: active portfolio project
Theme: Deep Ocean / Search Intelligence
Primary scope: Hannover and remote-in-Germany job-market intelligence

## Why this project exists

This project started from a real career problem: finding relevant jobs is easy in
small samples, but hard to do reliably over time. Interesting employers can be
hidden behind noisy aggregators, incomplete search terms, strict filters,
missing career-page evidence, or pipeline stops that look safe but create false
negatives.

The goal is therefore not to collect as many job postings as possible. The goal
is to build a personal Search Intelligence system that can explain what it
knows, what it missed, why a candidate was stopped, and what the next safe action
should be.

This is a portfolio project, but it is intentionally engineered like a product:
defensive acquisition, traceable decisions, explicit gates, governance around
agent behavior, and documentation that can survive more than one implementation
wave.

## What this project is

This repository is a personal job-market intelligence system for Hannover and
remote-in-Germany opportunities.

It is not a scraper demo and not a collection of one-off job-search scripts. The
current architecture combines market sensors, employer/source discovery,
evidence gates, agent-based repair planning, controlled connector activation,
and observability.

The product goal is to understand the relevant job market well enough to reduce
false negatives, avoid uncontrolled source expansion, and support better job and
application decisions.

## Current system in one sentence

```text
Market signals -> candidates -> origin/detail evidence -> gates/stops/repair
-> connector readiness -> controlled sources -> Bronze/Silver/Gold -> Control Center
```

## Deep Ocean design language

The documentation and UI use a Deep Ocean / Search Intelligence identity:

- **Sonar** for market sensing and signal discovery.
- **Depth** for evidence quality and confidence, not visual decoration.
- **Control surfaces** for gates, stops, approvals, and next safe actions.
- **Repair loops** for false-negative-aware learning instead of blind retries.
- **Calm technical visuals** over gaming, hype, or space-exploration metaphors.

The style should still be GitHub-friendly and maintainable. Mermaid diagrams and
plain Markdown are preferred over heavy assets unless a visual artifact has a
specific portfolio purpose.

## Core principles

- Defensive acquisition over aggressive crawling.
- Broad/tolerant raw discovery, strict promotion and activation gates.
- Evidence before connector build.
- Dry-run before apply.
- No commits on `main`.
- No CSV/Excel/export artifacts as pipeline inputs.
- Exports are reports, not source-of-truth handoffs.
- Planning/source-analysis documents are historical unless promoted into Current Truth.
- New agent-like artifacts require governance classification and capability-audit consideration.

## Current documentation entry point

Start here:

1. `docs/README.md`
2. `docs/architecture/current_system_overview.md`
3. `docs/architecture/system_diagrams.md`
4. `docs/architecture/architecture_document_status.md`
5. `docs/governance/README.md`
6. `docs/operations/runbook.md`

The old documentation surface is intentionally being rebaselined. The repository
contains many historically useful planning and source-analysis documents, but
those are no longer the primary architecture narrative.

## Main architecture areas

### Market sensors and discovery

The system ingests and observes job-market signals from defensive sources and
aggregators. Aggregators are treated as discovery inputs, not automatically
trusted source truth.

### Employer-origin candidates

Market signals can produce employer-origin candidates. Candidates need source
URL evidence, detail-page evidence, gate progression, and explicit approvals
before they can become active controlled sources.

### Evidence and gates

Evidence discovery and repair agents collect bounded, auditable evidence. Gates
evaluate evidence; they do not discover evidence themselves.

### Stopper reassessment

Stops are not blindly accepted as final truth. The stopper reassessment path can
audit whether a stop is valid, stale, over-sensitive, or false-negative-prone,
and can propose Stage-2 dry-run/apply repair plans.

### Connector chain

Connector build, validation, registration, final approval, and activation are
separate stages. Connector artifacts do not imply source activation.

### Data layers

- Bronze: tolerant/raw-first acquisition and preservation.
- Silver: canonical job representation.
- Gold: decision and observability read models.
- Control Center: product surface for candidate/source/agent/job state.

## Repository map

| Path | Purpose |
|---|---|
| `src/` | Production code and shared modules. |
| `scripts/` | CLI agents, checks, and operator commands. |
| `tests/` | Regression and contract tests. |
| `db/` | Database migrations and schema assets. |
| `docs/architecture/` | Current architecture entry points, contracts, document status, and diagrams. |
| `docs/governance/` | Agent governance, capability audit, drift guards, DOC/ADR strategy. |
| `docs/operations/` | Operator runbooks and maintenance workflows. |
| `docs/archive/` | Indexes for historical documentation areas. |
| `docs/planning/` | Historical build logs by default. |
| `docs/source_analysis/` | Historical/reference source-analysis material by default. |
| `exports/` | Ignored generated reports and runtime review artifacts. |

## Development workflow

Standard workflow for changes:

```bash
git switch main
git pull --ff-only
git switch -c feature/<descriptive-name>

# apply change
python -m pytest -q
git diff --check
git status --short

git add <files>
git diff --cached --check
git diff --cached --stat
git commit -m "<message>"

git push -u origin feature/<descriptive-name>
gh pr create --title "<title>" --body "<body>"

gh pr merge --squash --delete-branch
git switch main
git pull --ff-only
git fetch --prune
python -m pytest -q
git status --short
```

## Safety boundaries

Do not:

- commit directly on `main`,
- edit already-applied migrations,
- turn exports/CSV/Excel files into pipeline inputs,
- activate a source without explicit gates/approval,
- let repair agents approve their own output,
- treat historical planning notes as current architecture,
- add agent-like scripts without governance registration.

## Architecture contract anchors

Some repository tests intentionally assert that the README still points to the
active architecture and governance baselines.

Current anchors:

- `ARCH-001-SAFETY-SECURITY-STATE`
- `docs/governance/governance_foundation.md`
- `docs/planning/eo002b_candidate_reprocessing_url_finder_validation.md`

These anchors are retained during DOC-001 so older architecture-contract tests
continue to protect safety, governance, and candidate reprocessing context while
the Current Truth documentation layer is rebuilt.

- `docs/governance/documentation_drift_baseline.md`

## Local validation commands

Common validation:

```bash
python -m pytest -q
git diff --check
python scripts/check_governance_drift.py --json
```

Architecture/governance checks may be expanded over time.

## Documentation rebaseline status

DOC-001 is actively reducing documentation drift.

Current completed direction:

- create a reduced Current Truth layer,
- restore a portfolio-readable project motivation in the root README,
- mark planning and source-analysis material as historical by default,
- create archive indexes instead of mass-moving files too early,
- rebuild current architecture/system diagrams,
- rebaseline ADRs before editing them individually.

## Current next work

Near-term documentation work:

1. finish DOC-001G architecture consolidation,
2. continue ADR status review,
3. move README contract anchors toward Current-Truth docs and tests,
4. selectively deprecate or move historical docs only after Current Truth is stable.

Near-term product work after DOC-001:

1. STOP-002 stop taxonomy and repair strategy registry,
2. controlled EO/connector candidate chain progression,
3. continued false-negative and source-quality maturity work.
