# DRJ branch dispositions — semantic harvest batch 3 (2026-09-16)

This document is project-side semantic evidence only. It does **not** create branch-retirement effect authority, delete authority, or permission to bypass DRJ runtime vetoes. Any eventual retirement remains subject to the DRJ standing-authority ceiling, fresh exact-ref/SHA revalidation, open-PR/protection/local-liveness/active-workflow vetoes, and post-effect reconciliation.

Authority boundary for this review: branch age, naming, inactivity, or temporary intent alone are not terminal evidence. The four records below are terminal only because their unique value is either explicitly obsolete after a later accepted canonical product closure, or has been harvested into durable run evidence.

## New exact terminal records

### `agent/f2-acceptance-cohort`

- exact head: `dc923a3577533dcd1ab8190f295bbe0476ab4dff`
- semantic disposition: `DEPRECATED`
- unique history disposition: `REJECTED`
- unique content at review: two historical F2 acceptance workflow files, pinned to the older F2 product SHA/release context.
- terminal evidence: the later canonical F2 implementation/acceptance path landed through PR #862 / commit `fb06e1191ae044d0c0547e9136c7860b097bdf5b`; current project truth in `docs/planning/active/f3_truth_lifecycle_hardening.md` states that F2 is operator-accepted on installed Desktop v1.0.23 and `CR-F2-001` is CLOSED. The old workflow carrier is therefore not retained as project implementation or future execution authority.
- interpretation: `REJECTED` is deliberate. This record does not claim byte-for-byte canonicalization of the old workflow; it records that its remaining unique workflow implementation is obsolete after the stronger accepted canonical F2 closure.

### `agent/f2-operator-cold-e2e`

- exact head: `cd850f5e32fdc61fdd0a1b9f148e3ea4347e3b25`
- semantic disposition: `DEPRECATED`
- unique history disposition: `REJECTED`
- unique content at review: historical F2 cold/operator diagnostic workflow content pinned to the older F2 product context.
- terminal evidence: the later canonical F2 path landed through PR #862 / commit `fb06e1191ae044d0c0547e9136c7860b097bdf5b`; current project truth records installed Desktop v1.0.23 operator acceptance and `CR-F2-001` CLOSED.
- interpretation: the unique old diagnostic workflow is intentionally not promoted into current project truth. The accepted canonical F2 path supersedes its execution role, so its remaining unique history is explicitly rejected rather than described as canonicalized.

### `agent/rcc-step1-wsl-inventory-001a`

- exact head: `ba154ec46b8dd9ad0c0da4eb28c2baaa444bffa1`
- semantic disposition: `RETIRE`
- unique history disposition: `HARVESTED`
- unique content at review: one explicitly one-time, read-only RCC WSL physical-runner inventory workflow.
- exact execution evidence: Actions run `34631891824`, job `103370451888`, completed `success` on the exact branch head.
- harvested observations from that run: `15` runner registrations, `41` runner payload roots, `26` payload roots without registration, `15` systemd runner units, `15` systemd runner unit files, `31` listener/worker-related processes, and `scan_errors=[]`. The run also exposed UTF-8-BOM parse failures in the `.runner` registration files, making the repository registration map `UNKNOWN` in that diagnostic snapshot. Tool observations included Python 3.12.3, .NET SDK 10.0.112, Docker 29.7.2, GitHub CLI 2.45.0, PowerShell 7.6.5 and jq 1.7; the shared runner-toolchain cache contained Godot 4.7.1 and the PED Kaggle tooling was present.
- artifact evidence: `rcc-step1-wsl-fleet-inventory`, artifact id `10276845632`, uploaded successfully; artifact ZIP SHA256 `3041282d418a9b48eec493fb77dbf2059fce0281c5712ee81099f54357d1c65b`.
- interpretation: the workflow was an evidence carrier, not durable product behavior. Its relevant unique value is captured above and remains attributable to the immutable Actions run even after artifact retention expires.

### `rcc-workload-ready-jap-canary`

- exact head: `b575c3f057792ca48927721435460f7e1a5f012d`
- semantic disposition: `RETIRE`
- unique history disposition: `HARVESTED`
- unique content at review: one temporary JAP warm-runtime probe workflow.
- exact execution evidence: Actions run `34356910371`, job `102483805186`, completed `success` on the exact branch head.
- harvested observations from the pre-setup probe: runner `job-pipeline-runtime-warm-01-linux` on Linux; `python` was not in PATH; `node` was not in PATH; `npm` resolved through `/mnt/c/Program Files/nodejs/npm` and reported 10.9.3; the runner tool cache already contained Node `22.23.2` at `_work/_tool/node/22.23.2/x64/bin/node`.
- interpretation: this was a bounded diagnostic used to establish the pre-setup runtime state. The diagnostic result is now durable here and in the immutable successful Actions run; the temporary workflow itself has no continuing execution role.

## Still intentionally unresolved / preserved

The following reviewed refs remain outside machine-terminal scope because the evidence is insufficient to declare their unique value fully harvested, canonicalized, or rejected:

- `agent/676-deterministic-connector-builder@14e60cd24cfdcc37a41ef9171e6ce269553c69ed` — 36 unique commits / 23 files of real acquisition implementation and tests; PR #678 is closed-unmerged, while current ACQ-GENERALIZATION-90 truth remains retained/resumable. KEEP / HARVEST_PENDING.
- `agent/p1-connector-delivery-audit@857b805b4b3368e59875fff4253712c95d2b9bba` — two unique diagnostic implementation/test commits; PR #836 is closed-unmerged with no durable rejection or absorption handoff. KEEP / HARVEST_PENDING.
- `agent/winapp-020-prebuilt-frontend-startup@98e735b27d684084c8b5218884da87ddab29cf09` — four unique product/installer commits. Current `main` still requires Node 22 activation in `scripts/run_jap_windows_control_center.sh`, so the branch's Node-free prebuilt-frontend startup behavior is not proven absorbed or rejected. KEEP / HARVEST_PENDING.
- `tmp/jap-lockgen-final@d8d2f50ed783afac87e9dd223400c10e20c0da8f` — the temporary lock generator succeeded in run `34356684061` and produced `LOCK_SHA256=63789635ae420889ae34e51bc2e2e39219a474e91001da688f038135fe196437`, but neither JAP nor RCC current truth contains a proven consumption/canonicalization of that generated lock. Successful generation alone is not harvest evidence. KEEP / HARVEST_PENDING.

## Result

This batch publishes exactly four new SHA-bound project-side terminal decisions and deliberately preserves the other four reviewed HARVEST_PENDING branches. It performs no branch effect and grants no effect authority.
