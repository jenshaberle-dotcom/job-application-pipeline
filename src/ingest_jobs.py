from src.connectors.bundesagentur import BundesagenturConnector
from src.ingestion.repository import JobIngestionRepository
from src.ingestion.runner import JobIngestionRunner


PROFILE_NAME = "ba_data_engineer_30629_50km"


def main() -> None:
    repository = JobIngestionRepository()
    connector = BundesagenturConnector()

    runner = JobIngestionRunner(
        repository=repository,
        connector=connector,
    )

    runner.run(profile_name=PROFILE_NAME)


if __name__ == "__main__":
    main()
