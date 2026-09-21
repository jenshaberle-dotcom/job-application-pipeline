import logging
import sys
from typing import Any

from src.connectors.base import JobSourceConnector, RawJobRecord, SearchTerm
from src.connectors.registry import SourceRole, source_role as registry_source_role
from src.ingestion.diagnostics import (
    classify_exception,
    format_ingestion_failure,
)
from src.ingestion.post_fetch_filter import (
    apply_keyword_filter,
    apply_multi_term_keyword_filter,
)
from src.ingestion.complete_inventory_lifecycle import (
    reconcile_verified_complete_inventory_health,
)
from src.ingestion.recurring_lifecycle_health import (
    reconcile_recurring_exact_detail_health,
)
from src.ingestion.repository import JobIngestionRepository
from src.ingestion.run_stage_telemetry import record_ingestion_stage_counts
from src.job_lifecycle_health import JobLifecycleHealthRepository
from src.search_intelligence.company_vocabulary import extract_vocabulary_terms


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


def record_market_sensor_evidence(
    repository: JobIngestionRepository,
    *,
    source_name: str,
    records: list[RawJobRecord],
    profile_name: str,
    search_term: str | None,
    ingestion_run_id: int,
) -> int:
    """Persist only company identity and optional vocabulary across the sensor boundary.

    Market-sensor job URLs, external job IDs and raw job titles are deliberately
    discarded here. The title column in the legacy market_evidence schema carries
    only the derived vocabulary projection until that schema is retired.
    """

    recorder = getattr(repository, "save_market_evidence", None)
    if recorder is None:
        return 0

    written = 0
    for record in records:
        company_name = get_record_display_company(record)
        if company_name == MISSING_DISPLAY_VALUE:
            continue

        display_title = get_record_display_title(record)
        vocabulary_terms = (
            extract_vocabulary_terms(display_title)
            if display_title != MISSING_DISPLAY_VALUE
            else ()
        )
        evidence_id = recorder(
            evidence_source="market_sensor_ingestion",
            evidence_kind="market_sensor_company_sighting",
            source_name=source_name,
            company_name=company_name,
            title=" ".join(vocabulary_terms),
            evidence_url=None,
            search_profile_name=profile_name,
            search_term=search_term,
            ingestion_run_id=ingestion_run_id,
            raw_job_external_id=None,
            evidence={
                "boundary": {
                    "company_identity_only": True,
                    "vocabulary_only": True,
                    "sensor_url_forwarded": False,
                    "raw_job_identity_forwarded": False,
                    "bronze_write": False,
                    "silver_write": False,
                    "source_activation": False,
                    "scheduler_change": False,
                },
                "vocabulary_terms": list(vocabulary_terms),
            },
        )
        if evidence_id is not None:
            written += 1
    return written


class JobIngestionRunner:
    def __init__(
        self,
        repository: JobIngestionRepository,
        connector: JobSourceConnector,
        health_repository: JobLifecycleHealthRepository | None = None,
        source_role: SourceRole | None = None,
    ) -> None:
        self.repository = repository
        self.connector = connector
        self.health_repository = health_repository
        if source_role is not None:
            self.source_role = source_role
        else:
            try:
                self.source_role = registry_source_role(connector.source_name)
            except ValueError:
                self.source_role = None

    def run(self, profile_name: str) -> None:
        search_terms = self.repository.load_active_search_terms(profile_name)

        if not search_terms:
            raise ValueError(f"No active search terms found for profile: {profile_name}")

        if self.source_role == SourceRole.SENSOR:
            self.run_market_sensor_observation(search_terms)
            return

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

            if not self.connector.capabilities.supports_keyword:
                records = apply_keyword_filter(
                    records=records,
                    search_term=search_term.search_term,
                )

            record_ingestion_stage_counts(
                self.repository,
                ingestion_run_id=ingestion_run_id,
                connector_record_count=loaded_before_local_filter,
                post_filter_count=len(records),
            )

            inserted_count = 0
            duplicate_count = 0

            print("---")
            print(f"Profile: {profile.profile_name}")
            print(f"Search term: {search_term.search_term}")
            print(f"Final URL: {requested_url}")
            print(f"{loaded_before_local_filter} Jobs geladen vor lokaler Filterung")

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

    def run_market_sensor_observation(
        self,
        search_terms: list[tuple[Any, SearchTerm]],
    ) -> None:
        """Run one source-role SENSOR without creating Product job records."""

        if (
            self.connector.capabilities.supports_full_fetch
            and not self.connector.capabilities.supports_keyword
        ):
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
                diagnostic = classify_exception(exc=exc, error_stage="source_request")
                self.repository.fail_ingestion_run(
                    ingestion_run_id=ingestion_run_id,
                    error_message=diagnostic.error_message,
                    error_type=diagnostic.error_type,
                    error_stage=diagnostic.error_stage,
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
            record_ingestion_stage_counts(
                self.repository,
                ingestion_run_id=ingestion_run_id,
                connector_record_count=loaded_before_local_filter,
                post_filter_count=len(records),
            )
            written = record_market_sensor_evidence(
                self.repository,
                source_name=self.connector.source_name,
                records=records,
                profile_name=profile.profile_name,
                search_term=None,
                ingestion_run_id=ingestion_run_id,
            )
            self.repository.finish_ingestion_run(
                ingestion_run_id=ingestion_run_id,
                total_loaded=len(records),
                inserted_count=0,
                duplicate_count=0,
            )
            print("---")
            print(f"Market sensor profile: {profile.profile_name}")
            print(f"Observed records: {len(records)}")
            print(f"Company/vocabulary evidence written: {written}")
            print("Product job writes: 0")
            return

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
                diagnostic = classify_exception(exc=exc, error_stage="source_request")
                self.repository.fail_ingestion_run(
                    ingestion_run_id=ingestion_run_id,
                    error_message=diagnostic.error_message,
                    error_type=diagnostic.error_type,
                    error_stage=diagnostic.error_stage,
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
            record_ingestion_stage_counts(
                self.repository,
                ingestion_run_id=ingestion_run_id,
                connector_record_count=loaded_before_local_filter,
                post_filter_count=len(records),
            )
            written = record_market_sensor_evidence(
                self.repository,
                source_name=self.connector.source_name,
                records=records,
                profile_name=profile.profile_name,
                search_term=search_term.search_term,
                ingestion_run_id=ingestion_run_id,
            )
            self.repository.finish_ingestion_run(
                ingestion_run_id=ingestion_run_id,
                total_loaded=len(records),
                inserted_count=0,
                duplicate_count=0,
            )
            print("---")
            print(f"Market sensor profile: {profile.profile_name}")
            print(f"Search term: {search_term.search_term}")
            print(f"Observed records: {len(records)}")
            print(f"Company/vocabulary evidence written: {written}")
            print("Product job writes: 0")

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

        full_fetch_records = list(records)
        loaded_before_local_filter = len(records)
        records = apply_multi_term_keyword_filter(
            records=records,
            search_terms=active_terms,
        )
        loaded_after_local_filter = len(records)

        record_ingestion_stage_counts(
            self.repository,
            ingestion_run_id=ingestion_run_id,
            connector_record_count=loaded_before_local_filter,
            post_filter_count=loaded_after_local_filter,
        )

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

        if self.health_repository is not None:
            try:
                inventory_health = (
                    reconcile_verified_complete_inventory_health(
                        health_repository=self.health_repository,
                        source_name=self.connector.source_name,
                        observed_records=full_fetch_records,
                        ingestion_run_id=ingestion_run_id,
                    )
                )

                if inventory_health is None:
                    health_summary = reconcile_recurring_exact_detail_health(
                        health_repository=self.health_repository,
                        source_name=self.connector.source_name,
                        observed_records=full_fetch_records,
                        ingestion_run_id=ingestion_run_id,
                    )
                else:
                    health_summary = None

            except Exception as exc:
                self.repository.fail_ingestion_run(
                    ingestion_run_id=ingestion_run_id,
                    error_message=str(exc),
                    error_type=type(exc).__name__,
                    error_stage="recurring_lifecycle_health",
                )
                raise

            if inventory_health is not None:
                print(
                    "Recurring complete-inventory health: "
                    f"target={inventory_health.authority_target_key} "
                    f"targets={inventory_health.target_count} "
                    f"observed={inventory_health.observed_target_count} "
                    f"missing={inventory_health.missing_target_count} "
                    f"not_seen_writes="
                    f"{inventory_health.not_seen_write_count}"
                )
            else:
                assert health_summary is not None
                print(
                    "Recurring exact-detail health: "
                    f"targets={health_summary.target_count} "
                    f"observed={health_summary.observed_target_count} "
                    f"missing={health_summary.missing_target_count} "
                    f"probed={health_summary.probe_count} "
                    f"active_writes="
                    f"{health_summary.seen_active_write_count} "
                    f"closed_writes={health_summary.closed_write_count} "
                    f"unverifiable={health_summary.unverifiable_count}"
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
