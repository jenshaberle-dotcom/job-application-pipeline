from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_heartbeat_never_consumes_the_shared_physical_slot() -> None:
    workflow = (ROOT / ".github/workflows/warm-runner-heartbeat.yml").read_text(
        encoding="utf-8"
    )

    assert "schedule:" not in workflow
    assert "runs-on: [self-hosted" not in workflow
    assert "job-pipeline-runtime-linux" not in workflow
    assert "WARM_HEARTBEAT=COMPAT_TELEMETRY_ONLY" in workflow
    assert "HEARTBEAT_CAPACITY_AUTHORITY=NONE" in workflow
    assert "PHYSICAL_ACCEPTANCE_AUTHORITY=false" in workflow
    assert "SELF_HOSTED_SLOT_CONSUMPTION=NONE" in workflow


def test_real_canary_uses_exact_shared_facade_and_ephemeral_source() -> None:
    workflow = (ROOT / ".github/workflows/rcc-real-warm-canary.yml").read_text(
        encoding="utf-8"
    )

    assert 'default: rcc-general-linux-01' in workflow
    assert 'default: rcc-general-linux-01--jap' in workflow
    assert 'default: \'["self-hosted","rcc-general-linux-01--jap"]\'' in workflow
    assert "runs-on: ${{ fromJSON(inputs.runs_on_json) }}" in workflow
    assert "test \"$RUNNER_NAME\" = \"$RCC_FACADE_RUNNER\"" in workflow
    assert "RCC_EXACT_RUNNER_HANDOFF=PASS physical=" in workflow

    assert "uses: actions/checkout" not in workflow
    assert "git -C \"$source_root\" fetch --no-tags --depth=1 origin \"$RCC_SOURCE_SHA\"" in workflow
    assert "JAP_EPHEMERAL_SOURCE=PASS" in workflow
    assert "JAP_PERSISTENT_PROJECT_WORKSPACE=NONE" in workflow
    assert "JAP_EPHEMERAL_SOURCE_CLEANUP=PASS" in workflow
    assert "JAP_WORKLOAD_RESIDUE=NONE" in workflow
    assert "EPHEMERAL_EXACT_SOURCE_DELETE_ALWAYS" in workflow
    assert 'rm -rf -- "$GITHUB_WORKSPACE"' in workflow
    assert 'rm -rf -- "$JAP_SOURCE"' in workflow

    assert "RCC_SETUP_PYTHON=NONE" in workflow
    assert "RCC_PIP_INSTALL=NONE" in workflow
    assert "RCC_REMOTE_PIP_CACHE_RESTORE=NONE" in workflow
    assert "JAP_LOCAL_OSS_INSTALL_DURING_CANARY=NONE" in workflow
