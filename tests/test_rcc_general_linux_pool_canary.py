import json
from pathlib import Path


def test_rcc_real_warm_canary_accepts_exact_general_linux_pool_facades() -> None:
    workflow = Path(".github/workflows/rcc-real-warm-canary.yml").read_text(encoding="utf-8")

    assert '[[ "$RCC_PHYSICAL_RUNNER" =~ ^rcc-general-linux-0[1-5]$ ]]' in workflow
    assert 'test "$RCC_FACADE_RUNNER" = "$RCC_PHYSICAL_RUNNER--jap"' in workflow
    assert 'test "$RUNNER_NAME" = "$RCC_FACADE_RUNNER"' in workflow

    assert 'test "$RCC_PHYSICAL_RUNNER" = "rcc-general-linux-01"' not in workflow
    assert 'test "$RCC_FACADE_RUNNER" = "rcc-general-linux-01--jap"' not in workflow


def test_jap_runtime_slot_allows_shared_pool_burst_without_forcing_five_warm_members() -> None:
    contract = json.loads(Path(".rcc/runner-contract.json").read_text(encoding="utf-8"))
    slot = next(item for item in contract["slots"] if item["slot_id"] == "runtime-linux")

    assert slot["routing_labels"] == ["job-pipeline-runtime-linux"]
    assert slot["desired_count"] == 1
    assert slot["min_active"] == 0
    assert slot["max_active"] == 5
    assert slot["sleep_allowed"] is True
