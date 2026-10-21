from src.search_intelligence.source_population import reconcile_population


def test_census_and_sources_are_different_populations():
    result = reconcile_population([
        dict(company_key='a', factory_state='QUALIFIED', registered=True),
        dict(company_key='b', factory_state='TECHNICAL_GAP', registered=False),
    ], 853)
    assert result['census_candidate_count'] == 2
    assert result['factory_qualified_count'] == 1
    assert result['candidate_registry_unlinked_count'] == 1
    assert result['source_overview_count'] == 853
    assert result['factory_complete']
    assert result['same_population'] is False


def test_partial_campaign_is_not_complete_or_qualified():
    result = reconcile_population([dict(factory_state=None), dict(factory_state='ASSESSING')], 0)
    assert result['factory_checked_count'] == 0
    assert result['factory_qualified_count'] == 0
    assert not result['factory_complete']
    assert not reconcile_population([], 0)['factory_complete']
