from pathlib import Path


def test_live_scope_audit_is_read_only_and_exposes_origin_url() -> None:
    source = Path("scripts/run_product_v1_demo_live_scope_audit.py").read_text(
        encoding="utf-8"
    )
    assert '"database_writes": 0' in source
    assert '"network_requests": 0' in source
    assert '"provider_requests": 0' in source
    assert '"employer_origin_url"' in source
