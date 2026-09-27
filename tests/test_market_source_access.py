from src.search_intelligence.employer_discovery_census import CORE_SENSORS
from src.search_intelligence.market_source_access import (
    SOURCE_ACCESS,
    source_access_qualification,
)


def test_every_core_sensor_has_explicit_access_qualification():
    assert set(CORE_SENSORS) == set(SOURCE_ACCESS)


def test_goodjobs_is_real_source_identity_but_direct_automation_is_withheld():
    q = source_access_qualification("goodjobs")
    assert q.public_origin == "https://goodjobs.eu/"
    assert q.automation_authorized is False
    assert q.automation_status == "withheld"


def test_only_existing_ba_and_stepstone_paths_are_currently_authorized():
    authorized = [
        source
        for source, qualification in SOURCE_ACCESS.items()
        if qualification.automation_authorized
    ]
    assert authorized == ["bundesagentur_fuer_arbeit", "stepstone"]


def test_reviewed_boards_do_not_gain_direct_automation_authority_by_cohort_membership():
    for source in ("goodjobs", "xing", "meinestadt", "get_in_it", "jobvector"):
        assert source_access_qualification(source).automation_status == "withheld"
        assert source_access_qualification(source).automation_authorized is False
