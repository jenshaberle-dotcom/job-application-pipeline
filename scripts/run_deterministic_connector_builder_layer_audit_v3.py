from __future__ import annotations

from scripts import run_deterministic_connector_builder_layer_audit as base_audit
from scripts.run_origin_source_discovery_agent_v4 import run_for_company as run_origin_discovery_v4
from src.connectors.employer_origin_acquisition import (
    NavigationCandidate,
    canonical_url,
    explicit_root_delegated_listing_hosts,
)
from src.connectors.employer_origin_acquisition_v4 import (
    discover_navigation_candidates as discover_navigation_candidates_v4,
)
from src.connectors.employer_origin_ats_navigation import (
    authorized_ats_provider,
    provider_detail_urls,
    provider_listing_urls,
)


def discover_navigation_candidates_with_provider_inventory(
    page,
    *,
    allowed_hosts,
    known_detail_urls=(),
):
    """Compose already-authorized provider routes into builder inventory evidence.

    This wrapper grants no new provider or host authority.  It starts with the
    unchanged V4 navigation result, recognizes a provider only through the
    existing authorized-provider contract, and adds only routes emitted by the
    existing provider listing/detail adapters for that already-authorized page.
    Network execution and genuine-job acceptance remain owned by the unchanged
    V4 acquisition path.
    """

    result = list(
        discover_navigation_candidates_v4(
            page,
            allowed_hosts=allowed_hosts,
            known_detail_urls=known_detail_urls,
        )
    )
    seen = {canonical_url(item.url) for item in result}

    delegated_hosts = set(
        explicit_root_delegated_listing_hosts(
            page,
            allowed_hosts=allowed_hosts,
        )
    )
    provider = authorized_ats_provider(
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=allowed_hosts,
        delegated_hosts=delegated_hosts,
    )
    if provider is None:
        return tuple(result)

    for url in provider_detail_urls(
        provider=provider,
        page_url=page.final_url,
        body=page.html,
        allowed_hosts=allowed_hosts,
    ):
        clean = canonical_url(url)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(
            NavigationCandidate(
                url,
                "detail",
                f"{provider}_provider_detail_evidence",
                "",
                False,
            )
        )

    for url in provider_listing_urls(
        provider=provider,
        page_url=page.final_url,
        html=page.html,
        allowed_hosts=allowed_hosts,
    ):
        clean = canonical_url(url)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(
            NavigationCandidate(
                url,
                "listing",
                f"{provider}_provider_listing_evidence",
                "",
                False,
            )
        )

    return tuple(result)


def main() -> int:
    # Preserve the balanced V2 origin planner and every acquisition/proof rule.
    # Only make the builder's inventory observation compose already-existing
    # provider-route adapters, preventing provider evidence from being discarded
    # between the provider and inventory layers.
    base_audit.run_origin_discovery = run_origin_discovery_v4
    base_audit.discover_navigation_candidates = (
        discover_navigation_candidates_with_provider_inventory
    )
    return base_audit.main()


if __name__ == "__main__":
    raise SystemExit(main())
