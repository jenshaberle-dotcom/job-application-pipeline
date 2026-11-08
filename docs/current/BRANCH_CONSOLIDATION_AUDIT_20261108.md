# JAP Branch consolidation audit — 2026-11-08

This audit is **read-only repository analysis** and not a claim of completed consolidation.

## Verified repository state

| Scope | Observation |
|---|---|
| Classic `main` | `819e0df0a9ea8c92866dfdb2ac4f17acdee0d10f` (2026-10-05) |
| Classic remote branches | 272, including historical agent/proof/demo/governance branches |
| Classic open PRs | 15 |
| Runtime remote branches | 427 (private repository; branch names intentionally omitted here) |
| Runtime open PRs | 3 |
| Delete head branches after merge | **Already enabled** (`delete_branch_on_merge=true`) in **both** GitHub repositories |
| Experiment branch | `experiment/hannover-browser-agent-discovery-20261108`, based on current Classic main through the prior Hannover PoC lineage |
| Production main changed by this experiment | **No** |
| Remote branches deleted / PRs merged | **None** |

### Why not merge everything

Open PR branches are independent workstreams, not an ordered chain. Several PRs are unmergeable against current `main`; others have large deletions or overlap with already diverged governance. Merging every branch sequentially without rebase, CI, runtime qualification, source-lineage examination and safety proof would create an opaque integration with no reliable acceptance criteria.

The Runtime PR #400 (private) would remove over 40,000 lines against its current base; it must be kept out of an unattended mass merge. The newer Workchat/WSL governance draft is also a separate two-repository adoption decision.

## Open Classic PR review queue

| PR | Title | Changed files | GitHub mergeable | Proposed disposition |
|---|---|---:|---|---|
| [#1175](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1175) | Workspace hardcut: WSL-only Workchat reentry and remote delivery gate | 9 | Ja | Governance/WSL: Draft; Quellcode- und Runtime-Grenze abstimmen |
| [#1173](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1173) | Classic: connect Connector Factory to durable job delivery | 146 | Ja | E2E-/Factory-relevant: sehr großer PR (146 Dateien); isoliert prüfen, kein Sammel-Merge |
| [#1165](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1165) | Bind Windows RCC runtime to exact source and clean per-run checkouts | 7 | Ja | RCC Infrastruktur: separates RCC-/Windows-Gate, kein Browser-Experiment-Merge |
| [#1164](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1164) | Require qualified RCC packet paths in Classic Windows workflows | 8 | Ja | RCC Infrastruktur: Draft, separate Qualifikation |
| [#1160](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1160) | F6 hardcut: GPT-6.1 Sol quality-first CV and letter generation | 34 | Nein | außerhalb Experiment: CV/Brief-Hardcut, konfliktträchtig |
| [#1159](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1159) | Proof: RCC General-Windows Pool exact assignment | 1 | Ja | RCC Infrastruktur: Draft, separates Windows-Pool-Proof |
| [#1155](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1155) | Add read-only Cloud vNext census and recycle export | 4 | Ja | Census relevant: Read-only Census-Gate isoliert prüfen |
| [#1152](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1152) | Project connector fleet health and candidate disposition | 8 | Ja | Factory relevant: Fleet-Health isoliert prüfen |
| [#1149](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1149) | Hardcut: remove demo authority, preserve generic product capabilities | 151 | Nein | außerhalb Experiment: Demo-Authority-Retirement, große Deletion und Draft |
| [#1102](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1102) | Demo stability: avoid restart recovery on transient runtime slowness | 8 | Nein | außerhalb Experiment: alte Demo-Runtime-Stabilisierung |
| [#1087](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1087) | Freeze-II: fix external-index site targeting and rejection telemetry | 4 | Nein | Discovery relevant: External-index-Verbesserungen gegen Browser-Agent vergleichen |
| [#1060](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1060) | Freeze-II: promote SearXNG as defensive market-search transport | 5 | Nein | Discovery relevant: SearXNG-Transport gegenüber Brave benchmarken |
| [#1055](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/1055) | Freeze-II: make market sensors provider-agnostic and zero-cost-first | 10 | Nein | Discovery relevant: Provider-Agnostik prüfen |
| [#887](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/887) | F4B: reconcile Fit + Affinity before ranking mutation | 7 | Nein | außerhalb Experiment: altes F4B-Fit/Affinity-Draft |
| [#788](https://github.com/jenshaberle-dotcom/job-application-pipeline/pull/788) | DOC-RECOVERY: rebaseline project documentation to current product truth | 16 | Nein | außerhalb Experiment: großes Doku-Recovery außerhalb aktuellen Scopes |

*Mergeable is GitHub's point-in-time merge calculation, **not** a test result or merge authorization.*

## Concrete consolidation strategy

1. Freeze and back up currently unpublished local source with the existing JAP Local Safety Guard; never infer the host state from GitHub `main`.
2. Keep **one current main** and **one active browser-experiment branch** as the target architecture. Do not overwrite divergent branches merely to satisfy the branch-count target.
3. Validate the experiment against the identical Hannover employer population and old verified-source baseline. Record valid-job coverage, employer correctness, Factory definition, runtime extraction and cost/latency separately.
4. For open PRs relevant to the experiment, review #1173 (durable delivery), #1155 (Census), #1152 (fleet health), #1055 (provider-agnostic sensors), #1060 (SearXNG) and #1087 (external index) against their exact source SHAs and tests. Selective reimplementation/cherry-picking may be safer than merging entire PR trees.
5. Do not merge unrelated CV, demo, Windows RCC or governance hardcuts as side effects of the Browser Scout experiment.
6. After acceptance and successful validation, merge one cohesive, reviewed integration PR into main. GitHub will automatically delete its head branch because the settings are already enabled.
7. Run local Git history hygiene to classify remaining remote refs as **already merged** or **divergent**. Only previously reviewed, unchanged, non-PR **already-merged** refs are eligible for deletion. Divergent refs require explicit preserve/archive/merge decisions first.

### Local cleanup tooling

The separate standalone ZIP includes `hygiene/branch_cleanup.py` with a **plan-only default**. It reads Git ancestry and live open PRs from GitHub CLI, and can delete only reviewed SHA-matched merged remote heads after a separate confirmation. It cannot resolve divergent branches or certify feature completeness.

### Standalone UI

A local Python HTTP UI package has been delivered alongside the experiment: synthetic offline demo without credentials; real Browser Scout runs through the experiment checkout; per-company evidence, valid job and Factory decision cards; JSON report. The UI/branch-cleanup standalone package was tested locally (10 unit tests; rendered in Chromium). The local user's own code/data and real API credentials were not available for a live test. The standalone package is distributed separately from the GitHub source branch; the latter contains the agent, validator, tests and dependencies.

**Acceptance blocker:** With 272 Classic + 427 Runtime branches and 18 outstanding PRs, the target of only `main` and one experiment branch has **not** yet been achieved. No destructive operation was attempted to conceal that.
