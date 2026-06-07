from src.search_intelligence.origin_source_discovery_agent import generate_search_query_hints


def test_hannover_ruck_search_queries_include_hannover_re_alias() -> None:
    queries = generate_search_query_hints(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        target_location="Hannover",
    )
    assert '"Hannover Rück SE" Karriere Jobs Hannover' in queries
    assert '"hannover re" Karriere Jobs Hannover' in queries
    assert '"hannover-re" Karriere Jobs Hannover' in queries


def test_low_budget_query_order_uses_alias_in_second_query() -> None:
    queries = generate_search_query_hints(
        company_key="hannover_ruck",
        company_name="Hannover Rück SE",
        target_location="Hannover",
    )
    assert queries[0] == '"Hannover Rück SE" Karriere Jobs Hannover'
    assert queries[1] == '"hannover re" Karriere Jobs Hannover'
