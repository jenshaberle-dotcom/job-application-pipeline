from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
RETIRED = ROOT / ".github" / "retired-workflows" / "rcc-blue-cutover-20260916"

BLUE_LABEL = "job-pipeline-runtime-linux"
FREEZE_GUARD = "RCC_JAP_BLUE_ASSIGNMENT_FROZEN"
GREEN_FACADE = "rcc-general-linux-01--jap"

EXPECTED_ACTIVE_BLUE = {
    "f5-application-lifecycle-reconciliation.yml",
    "f5-candidate-supersession-preflight.yml",
    "f6-initial-assessment-materialization.yml",
    "freeze2-s0-source-truth-baseline.yml",
    "freeze2-s1-s2-residual-classification.yml",
    "freeze2-ingestion-stall-diagnostic.yml",
    "freeze2-linkedin-indeed-market-sensors.yml",
    "freeze2-sensor-candidate-expansion-review.yml",
    "p1-generic-origin-product-activate.yml",
    "p1-generic-origin-product-proof.yml",
    "p1-generic-origin-systematic-search.yml",
    "trusted-local-product-campaign.yml",
}

EXPECTED_RETIRED_BLUE = {
    "f2-bite-valuny-diagnostic.yml",
    "f2-bite-valuny-e2e.yml",
    "f2-dynamic-surface-diagnostic.yml",
    "f2-persisted-dynamic-cohort.yml",
    "f2-real-company-cohort.yml",
    "f3-truth-lifecycle-acceptance.yml",
    "f4a-profile-fit-diagnostic.yml",
    "f4a-r2-current-requirement-apply.yml",
    "f4a-r2-requirement-reconcile-plan.yml",
    "f4a-r3-bronze2e-apply.yml",
    "f4a-r3-bronze2e-requirement-audit.yml",
    "f4a-r3-silver-requirement-backfill-plan.yml",
    "f4a-r7-skill-reliability-audit.yml",
    "f4a-r8-operator-apply-v2.yml",
    "f4a-r8-operator-apply.yml",
    "f4a-r8-operator-preflight.yml",
    "f4a-requirement-evidence-audit.yml",
    "f4a-requirement-evidence-postapply-diagnostic.yml",
    "f4a-requirement-evidence-refresh-apply.yml",
    "f4a-requirement-evidence-refresh-plan.yml",
    "f4a-stale-current-lifecycle-revalidation.yml",
    "f4b-a1-c1-apply.yml",
    "f4b-personio-lifecycle-real-proof.yml",
    "f4b-readonly-cohort.yml",
    "f4c-current-source-health-proof.yml",
    "f4c-source-health-reconciliation.yml",
    "mlf005-live-db-proof.yml",
    "ml-pilot-001b-apply-label-migration.yml",
    "ml-pilot-001b-runtime-db-status-observer.yml",
    "ml-pilot-001b-runtime-db-status.yml",
    "rcc-warm-ownership-qualifier.yml",
}


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _blue_runs_on_files() -> set[str]:
    found: set[str] = set()
    for path in WORKFLOWS.glob("*.yml"):
        for line in _text(path).splitlines():
            stripped = line.strip()
            if stripped.startswith("runs-on:") and BLUE_LABEL in stripped:
                found.add(path.name)
                break
    return found


def test_only_current_blue_consumers_remain_executable_and_all_are_freezable() -> None:
    actual = _blue_runs_on_files()
    assert actual == EXPECTED_ACTIVE_BLUE

    for name in sorted(actual):
        text = _text(WORKFLOWS / name)
        blue_index = min(
            index
            for index, line in enumerate(text.splitlines())
            if line.strip().startswith("runs-on:") and BLUE_LABEL in line
        )
        lines_before_assignment = text.splitlines()[:blue_index]
        assert any(FREEZE_GUARD in line for line in lines_before_assignment), name

    print(f"JAP_BLUE_DIRECT_ASSIGNMENT_INVENTORY=PASS guarded={len(actual)}")
    print("JAP_BLUE_DIRECT_ASSIGNMENT_BYPASS=ABSENT_WHEN_FREEZE_TRUE")


def test_superseded_blue_workflows_are_preserved_but_not_executable() -> None:
    assert RETIRED.is_dir()
    actual = {path.name for path in RETIRED.glob("*.yml")}
    assert actual == EXPECTED_RETIRED_BLUE
    assert len(actual) == 31

    for name in actual:
        assert not (WORKFLOWS / name).exists(), name
        assert BLUE_LABEL in _text(RETIRED / name), name

    print("JAP_BLUE_RETIRED_WORKFLOWS=PASS count=31")


def test_heartbeat_canary_and_ci_have_no_legacy_blue_assignment() -> None:
    heartbeat = _text(WORKFLOWS / "warm-runner-heartbeat.yml")
    canary = _text(WORKFLOWS / "rcc-real-warm-canary.yml")
    ci = _text(WORKFLOWS / "ci.yml")

    assert "runs-on: [self-hosted" not in heartbeat
    assert BLUE_LABEL not in heartbeat
    assert "HEARTBEAT_CAPACITY_AUTHORITY=NONE" in heartbeat

    assert f'default: ["self-hosted","{GREEN_FACADE}"]' not in canary
    assert f'default: \'["self-hosted","{GREEN_FACADE}"]\'' in canary
    assert "runs-on: ${{ fromJSON(inputs.runs_on_json) }}" in canary
    assert "JAP_EPHEMERAL_SOURCE_CLEANUP=PASS" in canary

    assert f'\"{GREEN_FACADE}\"' in ci
    assert 'warm_runs_on_json: \'["self-hosted","Linux","X64","job-pipeline-runtime-linux"]\'' not in ci

    print("JAP_SHARED_CANARY_FACADE=PASS")
    print("JAP_PIPELINE_GREEN_SELECTOR=PASS")


