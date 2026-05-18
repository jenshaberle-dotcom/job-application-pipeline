from typing import Any

from src.connectors.base import JobSourceConnector, RawJobRecord
from src.ingestion.post_fetch_filter import apply_keyword_filter
from src.ingestion.repository import JobIngestionRepository


MISSING_DISPLAY_VALUE = "<missing>"


def get_nested_value(
    data: dict[str, Any],
    path: tuple[str, ...],
) -> str | None:
    current: Any = data

    for key in path:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    if current is None:
        return None

    value = str(current).strip()

    if not value:
        return None

    return value


def get_record_display_title(record: RawJobRecord) -> str:
    return (
        get_nested_value(record.raw_data, ("result_card", "title"))
        or get_nested_value(record.raw_data, ("job", "titel"))
        or get_nested_value(record.raw_data, ("job", "title"))
        or MISSING_DISPLAY_VALUE
    )


def get_record_display_company(record: RawJobRecord) -> str:
    return (
        get_nested_value(record.raw_data, ("result_card", "company_name"))
        or get_nested_value(record.raw_data, ("job", "arbeitgeber"))
        or get_nested_value(record.raw_data, ("job", "company_name"))
        or get_nested_value(record.raw_data, ("job", "company"))
        or MISSING_DISPLAY_VALUE
    )


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
            ingestion_run_id = self.repository.create_ingestion_run(
                source_name=self.connector.source_name,
                search_profile_id=profile.id,
            )

            try:
                records, requested_url = self.connector.fetch_jobs(profile, search_term)
            except Exception as exc:
                self.repository.fail_ingestion_run(
                    ingestion_run_id=ingestion_run_id,
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                raise

            self.repository.update_ingestion_run_requested_url(
                ingestion_run_id=ingestion_run_id,
                requested_url=requested_url,
            )

            loaded_before_local_filter = len(records)

            if not self.connector.capabilities.supports_keyword:
                records = apply_keyword_filter(
                    records=records,
                    search_term=search_term.search_term,
                )

            inserted_count = 0
            duplicate_count = 0

            print("---")
            print(f"Profile: {profile.profile_name}")
            print(f"Search term: {search_term.search_term}")
            print(f"Final URL: {requested_url}")
            print(f"{loaded_before_local_filter} Jobs geladen vor lokaler Filterung")

            if not self.connector.capabilities.supports_keyword:
                print(f"{len(records)} Jobs nach lokaler Keyword-Filterung")

            for record in records:
                new_id = self.repository.save_raw_job(
                    record=record,
                    ingestion_run_id=ingestion_run_id,
                    search_profile_id=profile.id,
                )

                raw_job_id = new_id

                if raw_job_id is None:
                    raw_job_id = self.repository.find_existing_raw_job_id(
                        source_name=record.source_name,
                        external_job_id=record.external_job_id,
                    )

                self.repository.save_job_observation(
                    record=record,
                    ingestion_run_id=ingestion_run_id,
                    raw_job_id=raw_job_id,
                )

                display_title = get_record_display_title(record)
                display_company = get_record_display_company(record)

                if new_id is None:
                    duplicate_count += 1
                    print(
                        f"Bereits vorhanden: {display_title} | "
                        f"{display_company}"
                    )
                    continue

                inserted_count += 1
                print(
                    f"Gespeichert: ID={new_id} | "
                    f"{display_title} | "
                    f"{display_company}"
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
