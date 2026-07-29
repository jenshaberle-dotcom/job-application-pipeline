from pathlib import Path

SCOPE = Path("docs/planning/active/origin_provider_event_runtime_001a.md").read_text(
    encoding="utf-8"
)


def test_origin_provider_runtime_scope_preserves_side_effect_boundaries() -> None:
    required = (
        "no provider call in implementation or CI",
        "no database mutation",
        "no candidate URL persistence",
        "no connector registration",
        "no source activation",
        "no scheduler mutation",
        "review artifacts are not pipeline inputs",
    )
    for statement in required:
        assert statement in SCOPE


def test_origin_provider_runtime_requires_private_sha_pinned_activation() -> None:
    assert "pinned by merge SHA" in SCOPE
    assert "private runtime" in SCOPE
    assert "only after its own" in SCOPE
