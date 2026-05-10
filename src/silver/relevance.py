from typing import Any


ROLE_TERMS = (
    "data engineer",
    "analytics engineer",
    "data platform",
    "data analyst",
    "bi engineer",
    "business intelligence",
    "etl",
    "elt",
    "machine learning engineer",
)

SKILL_TERMS = (
    "sql",
    "python",
    "etl",
    "elt",
    "data pipeline",
    "data warehouse",
    "data lake",
    "data platform",
    "azure",
    "aws",
    "gcp",
    "microsoft fabric",
    "databricks",
    "snowflake",
    "dbt",
    "airflow",
    "dagster",
    "prefect",
    "postgresql",
    "mongodb",
    "redis",
    "power bi",
    "tableau",
    "dashboard",
    "reporting",
    "api",
    "docker",
    "ci/cd",
)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).lower().strip()


def flatten_value(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        return " ".join(flatten_value(item) for item in value.values())

    if isinstance(value, list):
        return " ".join(flatten_value(item) for item in value)

    return normalize_text(value)


def build_relevance_text(raw_job: dict) -> str:
    raw_data = raw_job.get("raw_data") or {}
    job_data = raw_data.get("job", raw_data)

    return " ".join(
        part
        for part in (
            flatten_value(raw_job.get("source_name")),
            flatten_value(raw_job.get("source_url")),
            flatten_value(job_data.get("title")),
            flatten_value(job_data.get("titel")),
            flatten_value(job_data.get("description")),
            flatten_value(job_data.get("beschreibung")),
            flatten_value(job_data.get("content")),
            flatten_value(job_data.get("company_name")),
            flatten_value(job_data.get("arbeitgeber")),
            flatten_value(job_data.get("location")),
            flatten_value(job_data.get("arbeitsort")),
            flatten_value(job_data.get("metadata")),
            flatten_value(job_data.get("departments")),
            flatten_value(job_data.get("offices")),
        )
        if part
    )


def has_relevant_role_signal(text: str) -> bool:
    return any(term in text for term in ROLE_TERMS)


def count_skill_matches(text: str) -> int:
    return sum(1 for term in SKILL_TERMS if term in text)


def is_relevant_for_silver(raw_job: dict) -> bool:
    text = build_relevance_text(raw_job)

    if has_relevant_role_signal(text):
        return True

    return count_skill_matches(text) >= 2
