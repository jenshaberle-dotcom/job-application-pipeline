import psycopg
from collections import Counter

from src.config import get_database_config


ROLE_TERMS = (
    "data",
    "analytics",
    "insights",
    "business intelligence",
    "bi",
    "backend",
    "api",
    "platform",
    "developer experience",
    "cloud",
    "infrastructure",
    "machine learning",
    "ai",
    "security",
)

SKILL_TERMS = (
    "sql",
    "python",
    "etl",
    "elt",
    "data pipeline",
    "data warehouse",
    "data lake",
    "azure",
    "aws",
    "gcp",
    "databricks",
    "snowflake",
    "dbt",
    "airflow",
    "docker",
    "kubernetes",
    "api",
)

REMOTE_TERMS = (
    "remote",
    "home office",
    "work from home",
)

EUROPE_TERMS = (
    "germany",
    "berlin",
    "hamburg",
    "munich",
    "hannover",
    "cologne",
    "frankfurt",
    "dublin",
    "london",
    "paris",
    "amsterdam",
    "warsaw",
    "stockholm",
    "europe",
    "emea",
    "united kingdom",
    "ireland",
)


def normalize(value: object) -> str:
    if value is None:
        return ""

    return str(value).lower().strip()


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def matching_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    return [term for term in terms if term in text]


def classify_location(location: str) -> str:
    location_text = normalize(location)

    if not location_text:
        return "unknown"

    if contains_any(location_text, REMOTE_TERMS):
        return "remote"

    if contains_any(location_text, EUROPE_TERMS):
        return "europe_or_germany"

    if any(term in location_text for term in ("united states", " us", "usa", "san francisco", "seattle", "new york", "toronto", "canada")):
        return "north_america"

    if any(term in location_text for term in ("singapore", "bengaluru", "india", "mexico", "japan")):
        return "outside_europe"

    if location_text in ("n/a", "na", "none"):
        return "unknown"

    return "other"


def main() -> None:
    config = get_database_config()

    with psycopg.connect(**config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    source_name,
                    external_job_id,
                    source_url,
                    raw_data
                FROM raw_jobs
                WHERE source_name LIKE 'greenhouse:%'
                ORDER BY id;
                """
            )
            rows = cur.fetchall()

    total = len(rows)

    location_counter: Counter[str] = Counter()
    role_counter: Counter[str] = Counter()
    skill_counter: Counter[str] = Counter()

    role_relevant = 0
    skill_relevant = 0
    location_plausible = 0
    role_and_location = 0

    examples: list[tuple[int, str, str, list[str], list[str], str]] = []

    for row in rows:
        raw_job_id, source_name, external_job_id, source_url, raw_data = row

        job = raw_data.get("job", {})
        title = job.get("title", "")
        company_name = job.get("company_name", "")
        location = (job.get("location") or {}).get("name", "")

        text = " ".join(
            [
                normalize(title),
                normalize(company_name),
                normalize(location),
                normalize(source_url),
            ]
        )

        role_matches = matching_terms(text, ROLE_TERMS)
        skill_matches = matching_terms(text, SKILL_TERMS)
        location_class = classify_location(location)

        location_counter[location_class] += 1

        for term in role_matches:
            role_counter[term] += 1

        for term in skill_matches:
            skill_counter[term] += 1

        has_role_signal = bool(role_matches)
        has_skill_signal = len(skill_matches) >= 1
        has_plausible_location = location_class in ("remote", "europe_or_germany", "unknown")

        if has_role_signal:
            role_relevant += 1

        if has_skill_signal:
            skill_relevant += 1

        if has_plausible_location:
            location_plausible += 1

        if has_role_signal and has_plausible_location:
            role_and_location += 1

        if has_role_signal and len(examples) < 30:
            examples.append(
                (
                    raw_job_id,
                    title,
                    location,
                    role_matches,
                    skill_matches,
                    location_class,
                )
            )

    print("=== Greenhouse Bronze Diagnostics ===")
    print(f"Total Greenhouse raw jobs: {total}")
    print()

    print("Location classes:")
    for location_class, count in location_counter.most_common():
        print(f"- {location_class}: {count}")

    print()
    print("Role signal count:")
    print(f"- role_relevant: {role_relevant}")

    print()
    print("Skill signal count:")
    print(f"- skill_relevant: {skill_relevant}")

    print()
    print("Location plausibility:")
    print(f"- location_plausible: {location_plausible}")

    print()
    print("Combined:")
    print(f"- role_and_location: {role_and_location}")

    print()
    print("Most common role terms:")
    for term, count in role_counter.most_common(20):
        print(f"- {term}: {count}")

    print()
    print("Most common skill terms:")
    for term, count in skill_counter.most_common(20):
        print(f"- {term}: {count}")

    print()
    print("Example role-relevant jobs:")
    for raw_job_id, title, location, roles, skills, location_class in examples:
        print(
            f"- raw_job_id={raw_job_id} | {title} | {location} | "
            f"location_class={location_class} | roles={roles} | skills={skills}"
        )


if __name__ == "__main__":
    main()
