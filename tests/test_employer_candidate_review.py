from scripts.review_employer_source_candidates import (
    DEFAULT_CANDIDATES,
    CandidateHit,
    CANDIDATE_HIT_SQL,
    classify_false_negative_signal,
    classify_visibility,
    build_candidate_where_clause,
    matched_aliases_in_text,
    source_family,
    summarize_candidate,
)


def candidate_by_key(key):
    return next(candidate for candidate in DEFAULT_CANDIDATES if candidate.key == key)


def test_default_candidates_include_strategic_and_aggregator_discovered_groups() -> None:
    groups = {candidate.candidate_group for candidate in DEFAULT_CANDIDATES}
    keys = {candidate.key for candidate in DEFAULT_CANDIDATES}

    assert "strategic_expected" in groups
    assert "aggregator_discovered" in groups
    assert {"hdi", "rossmann", "finanz_informatik", "wertgarantie"}.issubset(keys)
    assert {"sumup", "cordes_graefe", "quantum_systems"}.issubset(keys)


def test_matched_aliases_are_case_insensitive() -> None:
    aliases = matched_aliases_in_text(
        "Senior Data Engineer at HDI Group in Hannover",
        ("HDI", "HDI Group", "ROSSMANN"),
    )

    assert aliases == ("HDI", "HDI Group")


def test_source_family_splits_source_targets() -> None:
    assert source_family("greenhouse:contentful") == "greenhouse"
    assert source_family("stepstone") == "stepstone"


def test_visibility_classification_distinguishes_missing_raw_and_silver() -> None:
    assert classify_visibility(raw_jobs=0, silver_jobs=0, skipped_raw_jobs=0) == "not_visible_current_db"
    assert classify_visibility(raw_jobs=2, silver_jobs=0, skipped_raw_jobs=2) == "raw_only_skipped_or_filtered"
    assert classify_visibility(raw_jobs=2, silver_jobs=0, skipped_raw_jobs=0) == "raw_only_not_promoted"
    assert classify_visibility(raw_jobs=2, silver_jobs=1, skipped_raw_jobs=1) == "visible_in_silver"


def test_strategic_missing_candidate_is_high_false_negative_signal() -> None:
    hdi = candidate_by_key("hdi")

    assert (
        classify_false_negative_signal(hdi, "not_visible_current_db")
        == "high_expected_candidate_missing"
    )


def test_summarize_candidate_for_missing_strategic_candidate_recommends_origin_review() -> None:
    summary = summarize_candidate(candidate_by_key("hdi"), [])

    assert summary.visibility_status == "not_visible_current_db"
    assert summary.false_negative_signal == "high_expected_candidate_missing"
    assert summary.likely_gap_type == "source_coverage_or_search_term_gap"
    assert summary.recommendation == "investigate_employer_origin_path_and_search_term_gap"


def test_summarize_candidate_for_silver_visible_candidate_is_covered() -> None:
    candidate = candidate_by_key("sumup")
    hit = CandidateHit(
        candidate_key="sumup",
        source_name="stepstone",
        raw_job_id=1,
        silver_job_id=10,
        decision="included",
        search_term="Analytics Engineer",
        raw_company_name="SumUp",
        raw_title="Analytics Engineer",
        silver_company_name="SumUp",
        silver_title="Analytics Engineer",
        source_url="https://example.test/job",
        fetched_at="2026-05-28T10:00:00+00:00",
        matched_aliases=("SumUp",),
    )

    summary = summarize_candidate(candidate, [hit])

    assert summary.visibility_status == "visible_in_silver"
    assert summary.false_negative_signal == "low_currently_visible"
    assert summary.recommendation == "covered_keep_in_overlap_and_source_value_monitoring"
    assert summary.source_names == "stepstone"
    assert summary.matched_search_terms == "Analytics Engineer"

def test_candidate_hit_sql_can_be_rendered_with_postgres_json_paths() -> None:
    candidate = candidate_by_key("hdi")
    where_clause, _ = build_candidate_where_clause(candidate)

    sql = CANDIDATE_HIT_SQL.replace("__WHERE_CLAUSE__", where_clause)

    assert "__WHERE_CLAUSE__" not in sql
    assert "#>> '{result_card,company_name}'" in sql
    assert "HDI" not in sql
    assert "LIKE LOWER(%s)" in sql

def test_candidate_where_clause_uses_bound_wildcard_parameters() -> None:
    candidate = candidate_by_key("hdi")
    where_clause, params = build_candidate_where_clause(candidate)

    assert "'%' || %s || '%'" not in where_clause
    assert "LIKE LOWER(%s)" in where_clause
    assert params
    assert all(param.startswith("%") and param.endswith("%") for param in params)

def test_sql_templates_escape_literal_percent_for_psycopg() -> None:
    from scripts.review_employer_source_candidates import (
        CANDIDATE_HIT_SQL,
        DEFAULT_CANDIDATES,
        SOURCE_COMPANY_DISCOVERY_SQL,
        build_candidate_where_clause,
    )

    where_clause, _ = build_candidate_where_clause(DEFAULT_CANDIDATES[0])
    candidate_sql = CANDIDATE_HIT_SQL.replace("__WHERE_CLAUSE__", where_clause)

    for sql in [candidate_sql, SOURCE_COMPANY_DISCOVERY_SQL]:
        assert "greenhouse:%'" not in sql
        assert "personio:%'" not in sql
        assert "greenhouse:%%'" in sql
        assert "personio:%%'" in sql
