from src.connectors.base import JobSourceConnector
from src.ingestion.repository import JobIngestionRepository


class JobIngestionRunner:
    def __init__(
        self,
        repository: JobIngestionRepository,
        connector: JobSourceConnector,
    ) -> None:
        self.repository = repository
        self.connector = connector

    def run(self, profile_name: str) -> None:
        search_terms = self.repository.load_active_search_terms(profile_name)

        if not search_terms:
            raise ValueError(f"No active search terms found for profile: {profile_name}")

        total_loaded_all = 0
        inserted_count_all = 0
        duplicate_count_all = 0

        for profile, search_term in search_terms:
            records, requested_url = self.connector.fetch_jobs(profile, search_term)

            ingestion_run_id = self.repository.create_ingestion_run(
                source_name=self.connector.source_name,
                search_profile_id=profile.id,
                requested_url=requested_url,
            )

            inserted_count = 0
            duplicate_count = 0

            print("---")
            print(f"Profile: {profile.profile_name}")
            print(f"Search term: {search_term.search_term}")
            print(f"Final URL: {requested_url}")
            print(f"{len(records)} Jobs geladen")

            for record in records:
                new_id = self.repository.save_raw_job(
                    record=record,
                    ingestion_run_id=ingestion_run_id,
                    search_profile_id=profile.id,
                )

                job = record.raw_data.get("job", {})

                if new_id is None:
                    duplicate_count += 1
                    print(
                        f"Bereits vorhanden: {job.get('titel')} | "
                        f"{job.get('arbeitgeber')}"
                    )
                    continue

                inserted_count += 1
                print(
                    f"Gespeichert: ID={new_id} | "
                    f"{job.get('titel')} | "
                    f"{job.get('arbeitgeber')}"
                )

            self.repository.finish_ingestion_run(
                ingestion_run_id=ingestion_run_id,
                total_loaded=len(records),
                inserted_count=inserted_count,
                duplicate_count=duplicate_count,
            )

            total_loaded_all += len(records)
            inserted_count_all += inserted_count
            duplicate_count_all += duplicate_count

            print(f"Ingestion Run ID: {ingestion_run_id}")
            print(f"Neue Jobs gespeichert: {inserted_count}")
            print(f"Bereits vorhandene Jobs übersprungen: {duplicate_count}")

        print("===")
        print(f"Gesamt geladen: {total_loaded_all}")
        print(f"Gesamt neu gespeichert: {inserted_count_all}")
        print(f"Gesamt bereits vorhanden: {duplicate_count_all}")
