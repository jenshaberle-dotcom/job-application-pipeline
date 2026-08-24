from src.search_intelligence.public_inventory_delegation import (
    PUBLIC_INVENTORY_DELEGATION_VERSION,
    authorize_public_inventory_candidate_host,
)


def _evidence(**overrides):
    values = {
        "employer_page_url": "https://careers.example.com/jobs",
        "authorized_employer_hosts": ("careers.example.com",),
        "inventory_host": "join.com",
        "inventory_provider": "join",
        "route_kind": "public_widget_bundle",
        "candidate_url": "https://join.com/companies/example/12345678-data-engineer",
        "candidate_observation_host": "join.com",
    }
    values.update(overrides)
    return authorize_public_inventory_candidate_host(**values)


def test_explicit_public_inventory_allows_one_exact_provider_host() -> None:
    evidence = _evidence()

    assert evidence.contract_version == PUBLIC_INVENTORY_DELEGATION_VERSION
    assert evidence.delegation_permitted is True
    assert evidence.delegated_host == "join.com"
    assert evidence.provider == "join"
    assert evidence.employer_page_authorized is True
    assert evidence.exact_inventory_candidate_host_match is True
    assert evidence.provider_consistent is True
    assert evidence.product_authority is False
    assert "authorized_employer_page_loaded_explicit_public_inventory" in evidence.reason_codes


def test_provider_recognition_never_authorizes_unbound_employer_page() -> None:
    evidence = _evidence(authorized_employer_hosts=("other.example.com",))

    assert evidence.delegation_permitted is False
    assert evidence.delegated_host is None
    assert "employer_page_not_currently_authorized" in evidence.reason_codes


def test_generic_script_or_asset_is_not_public_inventory_authority() -> None:
    evidence = _evidence(route_kind="explicit_script_asset")

    assert evidence.delegation_permitted is False
    assert evidence.delegated_host is None
    assert "explicit_public_inventory_route_kind_missing" in evidence.reason_codes


def test_candidate_must_be_observed_from_exact_inventory_host() -> None:
    evidence = _evidence(candidate_observation_host="cdn.join.com")

    assert evidence.delegation_permitted is False
    assert evidence.delegated_host is None
    assert "candidate_not_observed_from_exact_inventory_host" in evidence.reason_codes


def test_candidate_host_must_equal_inventory_host_not_merely_provider_family() -> None:
    evidence = _evidence(
        candidate_url="https://www.join.com/companies/example/12345678-data-engineer",
    )

    assert evidence.delegation_permitted is False
    assert evidence.delegated_host is None
    assert "candidate_not_observed_from_exact_inventory_host" in evidence.reason_codes


def test_inventory_and_candidate_provider_must_match() -> None:
    evidence = _evidence(
        inventory_host="boards.greenhouse.io",
        inventory_provider="greenhouse",
        candidate_url="https://join.com/companies/example/12345678-data-engineer",
        candidate_observation_host="boards.greenhouse.io",
    )

    assert evidence.delegation_permitted is False
    assert evidence.delegated_host is None
    assert "candidate_provider_not_recognized" in evidence.reason_codes or (
        "inventory_candidate_provider_mismatch" in evidence.reason_codes
    )


def test_http_candidate_never_receives_delegation() -> None:
    evidence = _evidence(
        candidate_url="http://join.com/companies/example/12345678-data-engineer",
    )

    assert evidence.delegation_permitted is False
    assert evidence.delegated_host is None
    assert "candidate_url_not_https" in evidence.reason_codes


def test_unknown_inventory_host_never_receives_delegation() -> None:
    evidence = _evidence(
        inventory_host="inventory.example.net",
        inventory_provider="join",
        candidate_url="https://inventory.example.net/jobs/12345678",
        candidate_observation_host="inventory.example.net",
    )

    assert evidence.delegation_permitted is False
    assert evidence.delegated_host is None
    assert "public_inventory_provider_not_recognized" in evidence.reason_codes
