"""No live network, DB, schedules, or external service calls in these tests."""
import json
from pathlib import Path

from src.connectors.hannover_tech_registry_poc import (
    Page, analyze, hannover_tech, population, related,
)

BASE = Path("examples/hannover-tech-registry-poc")


def inputs():
    def read(filename):
        return json.loads((BASE / filename).read_text(encoding="utf-8"))

    catalog = json.loads(
        Path("contracts/connector-capability-catalog-v1.json").read_text(encoding="utf-8")
    )
    return read("census.json"), read("openjobs.json"), read("boards.json"), catalog, read("replay.json")


def replay_getter(captures):
    def get(url):
        if url not in captures:
            raise OSError("no_recorded_capture")
        return Page(url, captures[url]["status"], captures[url]["body"])
    return get


def test_scope_membership_is_pair_bound_and_excludes_other_regions():
    census, *_ = inputs()
    assert [r["company_key"] for r in population(census)] == ["alpha", "beta", "gamma"]
    assert not hannover_tech({
        "scope_memberships": [
            {"geography": "BERLIN", "cohort": "TECH"},
            {"geography": "REGION_HANNOVER", "cohort": "SOCIAL"},
        ]
    })


def test_offline_registry_matching_never_implies_verified_source():
    census, openjobs, boards, catalog, _ = inputs()
    result = analyze(census, openjobs, boards, catalog)
    assert result["total"] == 3
    assert result["summary"]["registry_company_match"] == 2
    assert result["summary"]["registry_portal_candidate"] == 1
    assert result["summary"]["verified_portal"] == 0
    assert result["summary"]["factory_extracted"] == 0
    assert result["companies"][0]["status"] == "PORTAL_CANDIDATE_UNVERIFIED"


def test_synthetic_replay_covers_registry_to_factory_to_job_metadata():
    census, openjobs, boards, catalog, captures = inputs()
    result = analyze(census, openjobs, boards, catalog, get=replay_getter(captures))
    assert result["total"] == 3
    assert result["summary"] == {
        "registry_company_match": 2,
        "registry_portal_candidate": 1,
        "any_portal_candidate": 1,
        "verified_portal": 1,
        "verified_registry_portal": 1,
        "delta_verified_without_registry_portal": 0,
        "long_tail_registry_gap_closed": 0,
        "factory_recipe_built": 1,
        "factory_extracted": 1,
        "long_tail_registry_gap": 1,
        "long_tail_portal_gap": 2,
        "long_tail_factory_gap": 0,
    }
    alpha = result["companies"][0]
    assert alpha["company_name"] == "Alpha Analytics GmbH"
    assert alpha["website_evidence"] == "CORROBORATED_NAME_DOMAIN_AND_SITE_TITLE"
    assert alpha["status"] == "EXTRACTED"
    assert alpha["candidates"][0]["ownership_verified"] is True
    extraction = alpha["factory"][0]
    assert extraction["status"] == "EXTRACTION_PASS"
    assert extraction["definition_status"] == "PASS"
    assert len(alpha["candidates"][0]["evidence_ids"]) >= 2
    assert len(extraction["recipe_id"]) == 64
    assert extraction["job_count"] == 1
    assert extraction["job_sample"][0]["title"] == "Data Engineer"
    assert extraction["runtime_admitted"] is False
    assert extraction["production_activated"] is False
    assert extraction["persistable_definition"] is not None
    assert result["companies"][1]["status"] == "REGISTERED_WITHOUT_PORTAL"
    assert result["companies"][2]["status"] == "NO_REGISTER_MATCH"


def test_unconfirmed_corporate_website_blocks_registry_promotion():
    census, openjobs, boards, catalog, captures = inputs()
    # Website title + a registry URL on its own is not independent proof.
    openjobs[0]["website"] = "https://unrelated.example"
    result = analyze(census, openjobs, boards, catalog, get=replay_getter(captures))
    alpha = result["companies"][0]
    assert alpha["verified_portals"] == 0
    assert alpha["factory"] == []
    assert alpha["website_evidence"] == "OFFICIAL_SITE_IDENTITY_UNPROVEN"


def test_different_tenant_on_same_ats_vendor_is_not_equivalent():
    assert related(
        "https://boards.greenhouse.io/alphapoc",
        "https://boards.greenhouse.io/alphapoc/jobs/99",
    )
    assert not related(
        "https://boards.greenhouse.io/alphapoc",
        "https://boards.greenhouse.io/betapoc/jobs/99",
    )


def test_search_result_cannot_authorize_portal():
    census, openjobs, boards, catalog, captures = inputs()
    captures["https://alpha.example/"]["body"] = (
        "<html><title>Alpha Analytics</title><p>Visit our website</p></html>"
    )
    result = analyze(
        census, openjobs, boards, catalog, get=replay_getter(captures),
        search=lambda _: ["https://boards.greenhouse.io/alphapoc/jobs/99"],
    )
    assert result["companies"][0]["verified_portals"] == 0
    assert result["summary"]["factory_extracted"] == 0


def test_ambiguous_census_websites_require_review():
    census, openjobs, boards, catalog, captures = inputs()
    census["candidates"][0]["websites"] = [
        "https://alpha.example", "https://unrelated.example",
    ]
    result = analyze(census, openjobs, boards, catalog, get=replay_getter(captures))
    alpha = result["companies"][0]
    assert alpha["website"] == ""
    assert alpha["verified_portals"] == 0
    assert alpha["website_evidence"] == "AMBIGUOUS_CENSUS_WEBSITES"


def test_search_not_charged_when_official_ats_link_is_verified():
    census, openjobs, boards, catalog, captures = inputs()
    visited = []

    def search(name):
        visited.append(name)
        return []

    result = analyze(census, openjobs, boards, catalog,
                     get=replay_getter(captures), search=search)
    alpha = result["companies"][0]
    assert alpha["status"] == "EXTRACTED"
    assert alpha["search_attempted"] is False
    assert "Alpha Analytics GmbH" not in visited


def test_unmeasured_portal_gap_is_not_reported_as_zero_or_full():
    census, openjobs, boards, catalog, _ = inputs()
    result = analyze(census, openjobs, boards, catalog)
    assert result["summary"]["long_tail_portal_gap"] is None
    assert result["summary"]["long_tail_factory_gap"] is None


def test_tenantless_vendor_root_cannot_authorize_any_ats_board():
    assert not related(
        "https://boards.greenhouse.io/",
        "https://boards.greenhouse.io/alphapoc/jobs/99",
    )
