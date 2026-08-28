from __future__ import annotations

from scripts.run_deterministic_connector_builder_layer_audit_v3 import (
    discover_navigation_candidates_with_provider_inventory,
)
from src.connectors.employer_origin_acquisition import parse_page


def _page(url: str, html: str):
    return parse_page(
        requested_url=url,
        final_url=url,
        status_code=200,
        html=html,
    )


def test_canonical_personio_root_exposes_existing_xml_inventory_route() -> None:
    page = _page(
        "https://example.jobs.personio.de/",
        "<html><head><title>Example Jobs</title></head><body></body></html>",
    )

    result = discover_navigation_candidates_with_provider_inventory(
        page,
        allowed_hosts={"example.jobs.personio.de"},
        known_detail_urls=(),
    )

    assert any(
        item.kind == "listing"
        and item.discovery_source == "personio_provider_listing_evidence"
        and item.url.startswith("https://example.jobs.personio.de/xml")
        for item in result
    )


def test_successfactors_visible_go_route_is_composed_as_inventory_evidence() -> None:
    page = _page(
        "https://jobs.example.successfactors.com/",
        """
        <html><body>
          <a href="/go/Engineering/12345/">All jobs</a>
        </body></html>
        """,
    )

    result = discover_navigation_candidates_with_provider_inventory(
        page,
        allowed_hosts={"jobs.example.successfactors.com"},
        known_detail_urls=(),
    )

    assert any(
        item.kind == "listing"
        and item.discovery_source == "successfactors_provider_listing_evidence"
        and "/go/Engineering/12345" in item.url
        for item in result
    )


def test_unrecognized_surface_gains_no_provider_inventory_route() -> None:
    page = _page(
        "https://example.invalid/karriere",
        "<html><body><p>Careers</p></body></html>",
    )

    result = discover_navigation_candidates_with_provider_inventory(
        page,
        allowed_hosts={"example.invalid"},
        known_detail_urls=(),
    )

    assert not any("provider_" in item.discovery_source for item in result)
