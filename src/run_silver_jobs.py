from src.silver.repository import SilverJobRepository
from src.silver.transformer import transform_raw_job_to_silver


def main() -> None:
    repository = SilverJobRepository()

    raw_jobs = repository.load_unprocessed_raw_jobs(limit=100)

    if not raw_jobs:
        print("No unprocessed raw jobs found.")
        return

    transformed_count = 0

    for raw_job in raw_jobs:
        silver_job = transform_raw_job_to_silver(raw_job)
        repository.upsert_silver_job(silver_job)
        transformed_count += 1

        print(
            f"Silver job written: raw_job_id={silver_job['raw_job_id']} | "
            f"{silver_job['title']} | {silver_job['company_name']}"
        )

    print("---")
    print(f"Transformed raw jobs: {transformed_count}")


if __name__ == "__main__":
    main()
