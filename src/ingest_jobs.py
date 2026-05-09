import sys

from src.connectors.bundesagentur import BundesagenturConnector
from src.connectors.greenhouse import GreenhouseConnector
from src.ingestion.repository import JobIngestionRepository
from src.ingestion.runner import JobIngestionRunner


DEFAULT_PROFILE_NAME = "ba_data_engineer_30629_50km"


def create_connector(source_name: str):
    if source_name == "bundesagentur_fuer_arbeit":
        return BundesagenturConnector()

    if source_name.startswith("greenhouse:"):
        board_token = source_name.split(":", 1)[1]
        return GreenhouseConnector(board_token=board_token)

    raise ValueError(f"No connector configured for source: {source_name}")


def main() -> None:
    profile_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROFILE_NAME

    repository = JobIngestionRepository()
    profile = repository.load_search_profile(profile_name=profile_name)
    connector = create_connector(source_name=profile.source_name)

    runner = JobIngestionRunner(
        repository=repository,
        connector=connector,
    )

    runner.run(profile_name=profile_name)


if __name__ == "__main__":
    main()
