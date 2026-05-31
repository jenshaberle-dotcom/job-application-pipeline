import logging
import sys
from typing import Any

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchTerm
from src.ingestion.aggregator_discovery_filter import (
    filter_known_employer_origin_candidates,
    normalize_exclusion_keys,
)
from src.ingestion.diagnostics import (
    classify_exception,
    format_ingestion_failure,
)
from src.ingestion.post_fetch_filter import (
    apply_keyword_filter,
    apply_multi_term_keyword_filter,
)
from src.ingestion.repository import JobIngestionRepository


MISSING_DISPLAY_VALUE = "<missing>"


logger = logging.getLogger(__name__)


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


def load_aggregator_discovery_exclusion_keys(repository: JobIngestionRepository) -> set[str]:
    loader = getattr(repository, "load_aggregator_discovery_suppression_company_keys", None)
    if loader is None:
        loader = getattr(repository, "load_employer_origin_candidate_company_keys", None)
    if loader is None:
        return set()

    return normalize_exclusion_keys(loader())


def record_market_evidence_for_aggregator_records(
    repository: JobIngestionRepository,
    *,
    source_name: str,
    records: list[RawJobRecord],
    profile_name: str,
    search_term: str | None,
    ingestion_run_id: int,
) -> int:
    recorder = getattr(repository, "save_market_evidence", None)
    if recorder is None:
        return 0

    written = 0
    for record in records:
        company_name = get_record_display_company(record)
        title = get_record_display_title(record)
        if company_name == MISSING_DISPLAY_VALUE or title == MISSING_DISPLAY_VALUE:
            continue
        evidence_id = recorder(
            evidence_source="aggregator_ingestion",
            evidence_kind="aggregator_sighting",
            source_name=source_name,
            company_name=company_name,
            title=title,
            evidence_url=record.source_url,
            search_profile_name=profile_name,
            search_term=search_term,
            ingestion_run_id=ingestion_run_id,
            raw_job_external_id=record.external_job_id,
            evidence={
                "boundary": {
                    "market_evidence_only": True,
                    "bronze_write": False,
                    "source_activation": False,
                    "scheduler_change": False,
                }
            },
        )
        if evidence_id is not None:
            written += 1
    return written


def should_apply_aggregator_discovery_suppression(source_name: str) -> bool:
    return source_name == "stepstone"


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

        if (
            self.connector.capabilities.supports_full_fetch
            and not self.connector.capabilities.supports_keyword
        ):
            self.run_full_fetch_with_local_matching(search_terms)
            return

        total_loaded_all = 0
        inserted_count_all = 0
        duplicate_count_all = 0

        for profile, search_term in search_terms:
            ingestion_run_id = self.repository.create_ingestion_run(
                source_name=self.connector.source_name,
                search_profile_id=profile.id,
                search_term_id=search_term.id,
                search_term=search_term.search_term,
            )

            try:
                records, requested_url = self.connector.fetch_jobs(profile, search_term)
            except Exception as exc:
                diagnostic = classify_exception(
                    exc=exc,
                    error_stage="source_request",
                )

                self.repository.fail_ingestion_run(
                    ingestion_run_id=ingestion_run_id,
                    error_message=diagnostic.error_message,
                    error_type=diagnostic.error_type,
                    error_stage=diagnostic.error_stage,
                )

                logger.exception(
                    "Ingestion failed for profile '%s' and search term '%s'.",
                    profile.profile_name,
                    search_term.search_term,
                )

                print(
                    format_ingestion_failure(
                        profile_name=profile.profile_name,
                        source_name=self.connector.source_name,
                        diagnostic=diagnostic,
                    ),
                    file=sys.stderr,
                )

                raise

            self.repository.update_ingestion_run_requested_url(
                ingestion_run_id=ingestion_run_id,
                requested_url=requested_url,
            )

            loaded_before_local_filter = len(records)

            market_evidence_written = 0
            if should_apply_aggregator_discovery_suppression(self.connector.source_name):
                market_evidence_written = record_market_evidence_for_aggregator_records(
                    self.repository,
                    source_name=self.connector.source_name,
                    records=records,
                    profile_name=profile.profile_name,
                    search_term=search_term.search_term,
                    ingestion_run_id=ingestion_run_id,
                )

            if not self.connector.capabilities.supports_keyword:
                records = apply_keyword_filter(
                    records=records,
                    search_term=search_term.search_term,
                )

            suppressed_aggregator_records = []
            if should_apply_aggregator_discovery_suppression(self.connector.source_name):
                filter_result = filter_known_employer_origin_candidates(
                    records=records,
                    excluded_company_keys=load_aggregator_discovery_exclusion_keys(
                        self.repository
                    ),
                )
                records = filter_result.kept_records
                suppressed_aggregator_records = filter_result.suppressed_records

            inserted_count = 0
            duplicate_count = 0

            print("---")
            print(f"Profile: {profile.profile_name}")
            print(f"Search term: {search_term.search_term}")
            print(f"Final URL: {requested_url}")
            print(f"{loaded_before_local_filter} Jobs geladen vor lokaler Filterung")

            if market_evidence_written:
                print(f"Market Evidence Beobachtungen gespeichert: {market_evidence_written}")

            if not self.connector.capabilities.supports_keyword:
                print(f"{len(records)} Jobs nach lokaler Keyword-Filterung")

            if suppressed_aggregator_records:
                print(
                    f"{len(suppressed_aggregator_records)} StepStone-Ergebnisse "
                    "wegen bekannter Employer-Origin-Kandidaten unterdrückt"
                )
                for suppressed_record in suppressed_aggregator_records:
                    print(
                        "Unterdrückt: "
                        f"{suppressed_record.title or MISSING_DISPLAY_VALUE} | "
                        f"{suppressed_record.company_name}"
                    )

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

    def run_full_fetch_with_local_matching(
        self,
        search_terms: list[tuple[Any, SearchTerm]],
    ) -> None:
        profile = search_terms[0][0]
        active_terms = [search_term for _, search_term in search_terms]

        ingestion_run_id = self.repository.create_ingestion_run(
            source_name=self.connector.source_name,
            search_profile_id=profile.id,
            search_term_id=None,
            search_term=None,
        )

        try:
            records, requested_url = self.connector.fetch_jobs(
                profile,
                SearchTerm(search_term="*", id=None),
            )
        except Exception as exc:
            diagnostic = classify_exception(
                exc=exc,
                error_stage="source_request",
            )

            self.repository.fail_ingestion_run(
                ingestion_run_id=ingestion_run_id,
                error_message=diagnostic.error_message,
                error_type=diagnostic.error_type,
                error_stage=diagnostic.error_stage,
            )

            logger.exception(
                "Full-fetch ingestion failed for profile '%s'.",
                profile.profile_name,
            )

            print(
                format_ingestion_failure(
                    profile_name=profile.profile_name,
                    source_name=self.connector.source_name,
                    diagnostic=diagnostic,
                ),
                file=sys.stderr,
            )

            raise

        self.repository.update_ingestion_run_requested_url(
            ingestion_run_id=ingestion_run_id,
            requested_url=requested_url,
        )

        loaded_before_local_filter = len(records)
        records = apply_multi_term_keyword_filter(
            records=records,
            search_terms=active_terms,
        )
        loaded_after_local_filter = len(records)

        if profile.page_size and profile.page_size > 0:
            records = records[: profile.page_size]

        inserted_count = 0
        duplicate_count = 0

        print("---")
        print(f"Profile: {profile.profile_name}")
        print("Search terms: " + ", ".join(term.search_term for term in active_terms))
        print(f"Final URL: {requested_url}")
        print(f"{loaded_before_local_filter} Jobs geladen vor lokaler Filterung")
        print(f"{loaded_after_local_filter} Jobs nach lokaler Multi-Term-Filterung")
        if profile.page_size and profile.page_size > 0:
            print(f"{len(records)} Jobs nach page_size-Begrenzung")

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
            matched_terms = (
                record.raw_data
                .get("matching", {})
                .get("matched_terms", [])
            )

            matched_terms_display = ", ".join(matched_terms) or "<none>"

            if new_id is None:
                duplicate_count += 1
                print(
                    f"Bereits vorhanden: {display_title} | "
                    f"{display_company} | "
                    f"matched_terms: {matched_terms_display}"
                )
                continue

            inserted_count += 1
            print(
                f"Gespeichert: ID={new_id} | "
                f"{display_title} | "
                f"{display_company} | "
                f"matched_terms: {matched_terms_display}"
            )

        self.repository.finish_ingestion_run(
            ingestion_run_id=ingestion_run_id,
            total_loaded=len(records),
            inserted_count=inserted_count,
            duplicate_count=duplicate_count,
        )

        print(f"Ingestion Run ID: {ingestion_run_id}")
        print(f"Neue Jobs gespeichert: {inserted_count}")
        print(f"Bereits vorhandene Jobs übersprungen: {duplicate_count}")
        print("===")
        print(f"Gesamt geladen: {len(records)}")
        print(f"Gesamt neu gespeichert: {inserted_count}")
        print(f"Gesamt bereits vorhanden: {duplicate_count}")
