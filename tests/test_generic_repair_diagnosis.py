from __future__ import annotations

from scripts.run_generic_repair_diagnosis import (
    RelevantTable,
    TableColumn,
    choose_candidate_identity_column,
    choose_candidate_link_column,
    normalized_connect_kwargs,
    relevant_table_params,
    relevant_tables_where_clause,
    render_markdown,
    safe_report_stem,
    searchable_columns,
)


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


def test_safe_report_stem_is_filesystem_friendly() -> None:
    assert safe_report_stem("DIAG-001 adesso / Repair") == "diag_001_adesso_repair"
