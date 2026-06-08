from __future__ import annotations

from scripts.run_generic_repair_diagnosis import (
    RelevantTable,
    TableColumn,
    build_diagnosis_summary,
    build_portfolio_matrix_payload,
    choose_candidate_identity_column,
    choose_candidate_link_column,
    classify_linkage_pattern,
    normalized_connect_kwargs,
    relevant_table_params,
    relevant_tables_where_clause,
    render_markdown,
    render_portfolio_matrix_markdown,
    safe_report_stem,
    searchable_columns,
)


def sample_payload(company_key: str = "adesso", *, mentioned: int = 4, linked: int = 2) -> dict[str, object]:
    rows_mentioning = {f"mention_table_{idx}": [{"id": idx}] for idx in range(mentioned)}
    rows_linked = {
        f"linked_table_{idx}": {"link_column": "candidate_id", "rows": [{"candidate_id": 6}]}
        for idx in range(linked)
    }
    payload: dict[str, object] = {
        "generated_at": "2026-06-08T11:30:00+00:00",
        "company_key": company_key,
        "boundary": {},
        "schema_contract": {
            "candidate_identity_column": "id",
            "candidate_identity_values": [6],
        },
        "relevant_tables": [
            {
                "table_name": "employer_origin_source_candidates",
                "searchable_columns": ["company_key", "candidate_url"],
                "candidate_link_column": None,
            }
        ],
        "representative_candidate_rows": [{"id": 6, "company_key": company_key}],
        "rows_mentioning_company": rows_mentioning,
        "rows_linked_by_candidate_id": rows_linked,
        "generic_diagnosis_questions": ["Would this help peer candidates?"],
    }
    payload["summary"] = build_diagnosis_summary(payload)
    return payload


def test_normalized_connect_kwargs_accepts_project_dict_shape() -> None:
    cfg = {
        "host": "localhost",
        "port": 5432,
        "dbname": "jobs",
        "user": "jens",
        "password": "secret",
        "ignored": "value",
    }

    assert normalized_connect_kwargs(cfg) == {
        "host": "localhost",
        "port": 5432,
        "dbname": "jobs",
        "user": "jens",
        "password": "secret",
    }


def test_choose_candidate_identity_column_supports_physical_id_and_candidate_id() -> None:
    assert choose_candidate_identity_column(("id", "company_key")) == "id"
    assert choose_candidate_identity_column(("candidate_id", "company_key")) == "candidate_id"


def test_choose_candidate_identity_column_fails_closed_for_unknown_schema() -> None:
    try:
        choose_candidate_identity_column(("company_key", "candidate_url"))
    except ValueError as exc:
        assert "No stable candidate identity column" in str(exc)
    else:  # pragma: no cover - explicit assertion message is clearer than pytest.raises here
        raise AssertionError("Expected ValueError for unknown candidate identity schema")


def test_relevant_table_filters_are_parameterized_for_psycopg() -> None:
    clause = relevant_tables_where_clause(("candidate", "gate"))
    assert clause == "table_name ilike %s or table_name ilike %s"
    assert relevant_table_params(("candidate", "gate")) == ("%candidate%", "%gate%")
    assert "%c" not in clause


def test_searchable_and_link_columns_are_generic() -> None:
    table = RelevantTable(
        "example_gate_table",
        (
            TableColumn("candidate_id", "integer"),
            TableColumn("company_key", "text"),
            TableColumn("stop_reason", "text"),
            TableColumn("created_at", "timestamp"),
        ),
    )

    assert choose_candidate_link_column(table.column_names) == "candidate_id"
    assert searchable_columns(table.column_names) == ("company_key", "stop_reason")


def test_render_markdown_summarizes_schema_and_boundaries() -> None:
    payload = {
        "generated_at": "2026-06-08T11:30:00+00:00",
        "company_key": "adesso",
        "schema_contract": {
            "candidate_identity_column": "id",
            "candidate_identity_values": [6],
        },
        "relevant_tables": [
            {
                "table_name": "employer_origin_source_candidates",
                "searchable_columns": ["company_key", "candidate_url"],
                "candidate_link_column": None,
            }
        ],
        "representative_candidate_rows": [{"id": 6, "company_key": "adesso"}],
        "rows_mentioning_company": {"employer_origin_source_candidates": [{"id": 6}]},
        "rows_linked_by_candidate_id": {},
        "generic_diagnosis_questions": ["Would this help peer candidates?"],
    }

    markdown = render_markdown(payload)

    assert markdown.startswith("# DIAG-001 Generic Repair Diagnosis")
    assert "This report is read-only" in markdown
    assert "Candidate identity column: `id`" in markdown
    assert "Would this help peer candidates?" in markdown


def test_build_diagnosis_summary_has_stable_contract_for_matrix_consumers() -> None:
    summary = build_diagnosis_summary(sample_payload(mentioned=10, linked=3))

    assert summary == {
        "company_key": "adesso",
        "candidate_identity_column": "id",
        "candidate_identity_values": [6],
        "candidate_row_count": 1,
        "relevant_table_count": 1,
        "tables_mentioning_company_count": 10,
        "tables_linked_by_candidate_id_count": 3,
        "mention_to_link_gap": 7,
        "linkage_pattern": "weak_candidate_lifecycle_linkage",
    }


def test_classify_linkage_pattern_is_generic_and_deterministic() -> None:
    assert classify_linkage_pattern(mention_count=0, linked_count=0) == "no_observable_candidate_surface"
    assert classify_linkage_pattern(mention_count=5, linked_count=0) == "unlinked_evidence_surface"
    assert classify_linkage_pattern(mention_count=10, linked_count=3) == "weak_candidate_lifecycle_linkage"
    assert classify_linkage_pattern(mention_count=10, linked_count=7) == "partial_candidate_lifecycle_linkage"
    assert classify_linkage_pattern(mention_count=4, linked_count=4) == "strong_candidate_lifecycle_linkage"


def test_portfolio_matrix_payload_and_markdown_compare_multiple_companies() -> None:
    payload = build_portfolio_matrix_payload(
        [
            sample_payload("adesso", mentioned=17, linked=11),
            sample_payload("vhv_gruppe", mentioned=10, linked=3),
        ],
        benchmark_label="diag001b_test",
    )

    assert payload["campaign"] == "DIAG-001B Portfolio Failure Pattern Matrix"
    assert payload["summary"]["company_count"] == 2
    assert payload["summary"]["linkage_pattern_counts"] == {
        "partial_candidate_lifecycle_linkage": 1,
        "weak_candidate_lifecycle_linkage": 1,
    }
    assert payload["summary"]["companies_with_unlinked_or_weak_surfaces"] == ["vhv_gruppe"]

    markdown = render_portfolio_matrix_markdown(payload)

    assert markdown.startswith("# DIAG-001B Portfolio Failure Pattern Matrix")
    assert "`adesso`" in markdown
    assert "`vhv_gruppe`" in markdown
    assert "weak_candidate_lifecycle_linkage" in markdown


def test_safe_report_stem_is_filesystem_friendly() -> None:
    assert safe_report_stem("DIAG-001 adesso / Repair") == "diag_001_adesso_repair"
