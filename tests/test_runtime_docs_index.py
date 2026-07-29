from pathlib import Path

INDEX = Path("docs/runtime/README.md").read_text(encoding="utf-8")


def test_runtime_docs_index_keeps_private_runtime_outside_public_activation() -> None:
    assert "origin_provider_event_runtime.md" in INDEX
    assert "origin_provider_tools_checklist.md" in INDEX
    assert "private_origin_runtime_caller.example.yml" in INDEX
    assert "do not activate it from this public repository" in INDEX
