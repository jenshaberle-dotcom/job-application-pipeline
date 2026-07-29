from pathlib import Path

GUIDE = Path("docs/guides/origin_provider_event_runtime.md").read_text(
    encoding="utf-8"
)


def test_runtime_guide_keeps_private_runtime_outside_public_activation() -> None:
    assert "docs/reference/security/private_origin_runtime_caller.example.yml" in GUIDE
    assert "private runtime repository" in GUIDE
    assert "pin the reusable workflow reference" in GUIDE
    assert "artifacts are review output only and never pipeline input" in GUIDE
