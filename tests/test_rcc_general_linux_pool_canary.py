from pathlib import Path


def test_rcc_real_warm_canary_accepts_exact_general_linux_pool_facades() -> None:
    workflow = Path(".github/workflows/rcc-real-warm-canary.yml").read_text(encoding="utf-8")

    assert '[[ "$RCC_PHYSICAL_RUNNER" =~ ^rcc-general-linux-0[1-5]$ ]]' in workflow
    assert 'test "$RCC_FACADE_RUNNER" = "$RCC_PHYSICAL_RUNNER--jap"' in workflow
    assert 'test "$RUNNER_NAME" = "$RCC_FACADE_RUNNER"' in workflow

    assert 'test "$RCC_PHYSICAL_RUNNER" = "rcc-general-linux-01"' not in workflow
    assert 'test "$RCC_FACADE_RUNNER" = "rcc-general-linux-01--jap"' not in workflow
