from src.silver.relevance import (
    get_accessibility_matches,
    get_role_matches,
    get_skill_matches,
    is_relevant_for_silver,
)
from src.silver.repository import SilverJobRepository
from src.silver.transformer import (
    get_supported_source_patterns,
    transform_raw_job_to_silver,
)


def main() -> None:
    repository = SilverJobRepository()

    raw_jobs = repository.load_unprocessed_raw_jobs(
        limit=100,
        source_patterns=get_supported_source_patterns(),
    )

    if not raw_jobs:
        print("No unprocessed raw jobs found.")
        return

    transformed_count = 0
    skipped_count = 0

    for raw_job in raw_jobs:
        role_matches = get_role_matches(raw_job)
        skill_matches = get_skill_matches(raw_job)
        accessibility_matches = get_accessibility_matches(raw_job)

        if not is_relevant_for_silver(raw_job):
            repository.record_processing_decision(
                raw_job_id=raw_job["id"],
                decision="skipped",
                reason="not_relevant_for_silver",
                role_matches=role_matches,
                skill_matches=skill_matches,
                accessibility_matches=accessibility_matches,
            )
            skipped_count += 1

            print(
                f"Skipped raw job: raw_job_id={raw_job['id']} | "
                f"source={raw_job['source_name']} | "
                f"roles={role_matches} | "
                f"skills={skill_matches} | "
                f"accessibility={accessibility_matches}"
            )
            continue

        silver_job = transform_raw_job_to_silver(raw_job)
        repository.upsert_silver_job(silver_job)
        repository.record_processing_decision(
            raw_job_id=raw_job["id"],
            decision="included",
            reason="relevant_for_silver",
            role_matches=role_matches,
            skill_matches=skill_matches,
            accessibility_matches=accessibility_matches,
        )
        transformed_count += 1

        print(
            f"Silver job written: raw_job_id={silver_job['raw_job_id']} | "
            f"{silver_job['title']} | {silver_job['company_name']}"
        )

    print("---")
    print(f"Transformed raw jobs: {transformed_count}")
    print(f"Skipped raw jobs: {skipped_count}")


if __name__ == "__main__":
    main()
