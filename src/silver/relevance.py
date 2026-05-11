import re
from typing import Any


ROLE_PHRASES = (
    "data engineer",
    "analytics engineer",
    "data platform",
    "data analyst",
    "bi engineer",
    "business intelligence",
    "etl developer",
    "machine learning engineer",
    "data scientist",
    "data science",
    "data & insights",
    "data insights",
    "analytics",
    "backend engineer",
    "backend / api engineer",
    "backend/api engineer",
    "api engineer",
    "cloud engineer",
    "cloud security engineer",
    "platform engineer",
    "developer experience",
    "product platform",
    "infrastructure engineer",
    "ai security",
)

SKILL_PHRASES = (
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

ACCESSIBILITY_PHRASES = (
    "remote",
    "germany",
    "deutschland",
    "hannover",
    "hanover",
    "berlin",
    "hamburg",
    "munich",
    "münchen",
    "cologne",
    "köln",
    "frankfurt",
    "dublin",
    "ireland",
    "london",
    "united kingdom",
    "uk",
    "europe",
    "emea",
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


def phrase_matches(text: str, phrase: str) -> bool:
    normalized_phrase = normalize_text(phrase)

    if not normalized_phrase:
        return False

    escaped_phrase = re.escape(normalized_phrase)
    pattern = rf"(?<![a-z0-9]){escaped_phrase}(?![a-z0-9])"

    return re.search(pattern, text) is not None


def matching_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
    return [phrase for phrase in phrases if phrase_matches(text, phrase)]


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


def get_role_matches(raw_job: dict) -> list[str]:
    return matching_phrases(build_relevance_text(raw_job), ROLE_PHRASES)


def get_skill_matches(raw_job: dict) -> list[str]:
    return matching_phrases(build_relevance_text(raw_job), SKILL_PHRASES)


def get_accessibility_matches(raw_job: dict) -> list[str]:
    return matching_phrases(build_relevance_text(raw_job), ACCESSIBILITY_PHRASES)


def is_relevant_for_silver(raw_job: dict) -> bool:
    role_matches = get_role_matches(raw_job)
    skill_matches = get_skill_matches(raw_job)
    accessibility_matches = get_accessibility_matches(raw_job)

    if role_matches and accessibility_matches:
        return True

    if len(skill_matches) >= 2 and accessibility_matches:
        return True

    return False
