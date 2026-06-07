from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_doc001h_database_schema_overview_covers_current_domains():
    text = read("docs/database/schema_overview.md")

    required = [
        "Ingestion Core",
        "Employer-Origin Candidates",
        "Gate & Lifecycle Control",
        "Evidence & URL Discovery",
        "Connector Build Governance",
        "Search Intelligence Learning",
        "Aggregator & Market Sensors",
        "Origin Observation Learning",
        "Orchestration & Actions",
        "Gold / Control Center Views",
        "employer_origin_candidate_gate_reviews",
        "search_intelligence_orchestrator_runs",
        "search_intelligence_action_runs",
        "stepstone_company_discovery_cycle_reviews",
        "origin_job_page_observations",
        "candidate_origin_url_persistence_reviews",
        "schema_migrations",
    ]

    for phrase in required:
        assert phrase in text


def test_doc001h_database_constraints_are_documented_as_product_boundaries():
    text = read("docs/database/schema_overview.md")

    for phrase in [
        "Primary keys",
        "Foreign keys",
        "Unique constraints",
        "Check constraints",
        "Indexes",
        "Views",
        "product safety boundaries",
    ]:
        assert phrase in text


def test_doc001h_schema_relationships_include_mermaid_networks():
    text = read("docs/database/schema_relationships.md")

    assert text.count("```mermaid") >= 5
    for phrase in [
        "Ingestion, Bronze and Silver",
        "Employer-Origin Candidate and Gate Network",
        "Evidence, URL Discovery and Repair",
        "Connector Build and Approval Governance",
        "Search Intelligence Learning and Market Sensors",
        "Origin Observation and Pattern Learning",
        "Orchestrator, Actions and Audit",
    ]:
        assert phrase in text


def test_doc001h_database_entrypoint_and_legacy_warning_are_present():
    readme = read("docs/database/README.md")
    tables = read("docs/database/tables.md")

    assert "schema_overview.md" in readme
    assert "schema_relationships.md" in readme
    assert "not a complete inventory of the current schema" in readme
    assert "legacy core-table detail" in tables
    assert "not a complete Search Intelligence schema inventory" in tables


def test_doc001h_archive_path_status_classifies_chaotic_paths():
    text = read("docs/archive/documentation_path_status.md")

    for phrase in [
        "Current Truth entry",
        "Historical by default",
        "Archive candidate",
        "docs/planning/",
        "docs/source_analysis/",
        "docs/diagrams/",
        "docs/project_state/",
        "DOC-001I should perform the first physical archive pass",
    ]:
        assert phrase in text


def test_doc001h_navigation_links_database_and_archive_surfaces():
    docs_readme = read("docs/README.md")
    archive_readme = read("docs/archive/README.md")

    assert "docs/database/schema_overview.md" in docs_readme
    assert "docs/database/schema_relationships.md" in docs_readme
    assert "documentation_path_status.md" in archive_readme
