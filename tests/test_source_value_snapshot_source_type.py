from scripts.create_source_value_snapshot import source_type


def test_source_value_snapshot_classifies_enercity_as_employer_origin() -> None:
    assert source_type("enercity:discovery") == "employer_origin_career_site"


def test_source_value_snapshot_keeps_known_source_types() -> None:
    assert source_type("bundesagentur_fuer_arbeit") == "official_api"
    assert source_type("stepstone") == "commercial_aggregator"
    assert source_type("personio:eraneos") == "ats_company_board"
    assert source_type("finanz_informatik:hannover") == "employer_origin_career_site"
