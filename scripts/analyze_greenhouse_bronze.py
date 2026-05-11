from collections import Counter

import psycopg

from src.config import get_database_config
from src.silver.relevance import (
    get_accessibility_matches,
    get_role_matches,
    get_skill_matches,
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


def classify_location(location: str) -> str:
    location_text = normalize(location)

    if not location_text:
        return "unknown"

    if contains_any(location_text, REMOTE_TERMS):
        return "remote"

    if contains_any(location_text, EUROPE_TERMS):
        return "europe_or_germany"

    if any(
        term in location_text
        for term in (
            "united states",
            " us",
            "usa",
            "san francisco",
            "seattle",
            "new york",
            "toronto",
            "canada",
        )
    ):
        return "north_america"

    if any(
        term in location_text
        for term in (
            "singapore",
            "bengaluru",
            "india",
            "mexico",
            "japan",
        )
    ):
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
        location = (job.get("location") or {}).get("name", "")

        raw_job = {
            "id": raw_job_id,
            "source_name": source_name,
            "external_job_id": external_job_id,
            "source_url": source_url,
            "raw_data": raw_data,
        }

        role_matches = get_role_matches(raw_job)
        skill_matches = get_skill_matches(raw_job)
        accessibility_matches = get_accessibility_matches(raw_job)

        location_class = classify_location(location)

        location_counter[location_class] += 1

        for term in role_matches:
            role_counter[term] += 1

        for term in skill_matches:
            skill_counter[term] += 1

        has_role_signal = bool(role_matches)
        has_skill_signal = len(skill_matches) >= 1
        has_plausible_location = bool(accessibility_matches)

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
