from src.search_intelligence.discovery_coverage import assess


def test_coverage_gap_requests_more_sources_without_blocking_factory_learning():
    result=assess({"candidates":[{"geographies":["REGION_HANNOVER"],"cohorts":["TECH"]}]})
    assert result["status"]=="SOURCE_COVERAGE_GAP"
    assert result["coverage_gaps"]["BERLIN"]["additional_sources_required"] is True
    assert result["ml_scale_ready"] is False


def test_broad_population_passes_scale_gate():
    candidates=[]
    limits={"REGION_HANNOVER":250,"WOLFSBURG":50,"INGOLSTADT":50,"STUTTGART_REGION":100,"BERLIN":250,"MUNICH":250}
    for geography,count in limits.items():
        candidates.extend({"geographies":[geography],"cohorts":["TECH"]} for _ in range(count))
    result=assess({"candidates":candidates})
    assert result["status"]=="PASS"
    assert result["ml_scale_ready"] is True
