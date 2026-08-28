from __future__ import annotations

from urllib.parse import urlparse

from src.search_intelligence.origin_candidate_plan_v2 import (
    generate_company_url_candidates_v2,
    prioritized_domain_bases,
)


def _urls(company_key: str, company_name: str, *, max_candidates: int = 12) -> list[str]:
    return [
        item.url
        for item in generate_company_url_candidates_v2(
            company_key=company_key,
            company_name=company_name,
            max_candidates=max_candidates,
        )
    ]


def _hosts(urls: list[str]) -> set[str]:
    return {(urlparse(url).hostname or "").removeprefix("www.") for url in urls}


def test_kkh_short_brand_is_inside_active_budget() -> None:
    urls = _urls("kkh_kaufmannische_krankenkasse", "KKH Kaufmännische Krankenkasse")

    assert "https://kkh.de/" in urls
    assert "https://kkh.com/" in urls


def test_mtu_short_brand_is_promoted_even_when_already_identity_token() -> None:
    bases = prioritized_domain_bases(
        company_key="mtu_maintenance",
        company_name="MTU Maintenance",
    )
    urls = _urls("mtu_maintenance", "MTU Maintenance")

    assert bases[0] == "mtu"
    assert "https://mtu.de/" in urls


def test_iph_acronym_locality_hypothesis_is_inside_active_budget() -> None:
    bases = prioritized_domain_bases(
        company_key="iph_institut_fur_integrierte_produktion_hannover_ggmbh",
        company_name="IPH - Institut für Integrierte Produktion Hannover gGmbH",
    )
    urls = _urls(
        "iph_institut_fur_integrierte_produktion_hannover_ggmbh",
        "IPH - Institut für Integrierte Produktion Hannover gGmbH",
    )

    assert "iph" in bases
    assert "iph-hannover" in bases
    assert "https://iph-hannover.de/" in urls


def test_sport_alliance_compact_brand_gets_global_tld_budget() -> None:
    urls = _urls("sport_alliance", "Sport Alliance")

    assert "https://sportalliance.com/" in urls


def test_active_budget_is_not_single_host_family_monoculture() -> None:
    urls = _urls("loyos_bi", "loyos bi")

    assert len(_hosts(urls)) >= 4


def test_existing_explicit_aliases_remain_available() -> None:
    urls = _urls("hannover_ruck", "Hannover Rück SE")

    assert any("hannover-re.com" in url for url in urls)
