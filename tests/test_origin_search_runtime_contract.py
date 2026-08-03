from __future__ import annotations

from src.search_intelligence import adaptive_origin_search as adaptive
from src.search_intelligence.origin_search_runtime_contract import (
    install_origin_search_runtime_contract,
    is_followup_excluded_domain,
)


def test_legal_suffix_cleanup_does_not_leave_dangling_operator() -> None:
    install_origin_search_runtime_contract()

    variants = adaptive.brand_surface_variants(
        company_name="Clarios Germany GmbH & Co. KG",
        company_key="clarios_germany",
    )

    assert variants[0] == "clarios germany"
    assert "clariosgermanyand" not in variants
    assert all(not variant.endswith(("&", "+", "@")) for variant in variants)


def test_real_symbol_brand_is_preserved() -> None:
    install_origin_search_runtime_contract()

    variants = adaptive.brand_surface_variants(
        company_name="1&1",
        company_key="1_1",
    )

    assert variants[0] == "1&1"
    assert "1and1" in variants


def test_followup_queries_skip_noncorporate_and_shared_platform_hosts() -> None:
    install_origin_search_runtime_contract()

    queries = adaptive.domain_followup_queries(
        [
            "en.wikipedia.org",
            "kununu.com",
            "careers.smartrecruiters.com",
            "jobs.clarios.com",
            "clarios.com",
        ],
        maximum=4,
    )

    assert queries == (
        "site:jobs.clarios.com career",
        "site:jobs.clarios.com jobs",
        "site:clarios.com career",
        "site:clarios.com jobs",
    )
    assert is_followup_excluded_domain("en.wikipedia.org") is True
    assert is_followup_excluded_domain("careers.smartrecruiters.com") is True
    assert is_followup_excluded_domain("jobs.clarios.com") is False
