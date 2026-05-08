import json
import psycopg

from src.config import get_database_config
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm


class JobIngestionRepository:
    def __init__(self) -> None:
        self.connection_config = get_database_config()

    def get_connection(self):
        return psycopg.connect(**self.connection_config)

    def load_active_search_terms(
        self,
        profile_name: str,
    ) -> list[tuple[SearchProfile, SearchTerm]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        sp.id,
                        sp.profile_name,
                        sp.source_name,
                        sp.search_location,
                        sp.search_radius_km,
                        sp.offer_type,
                        sp.page_size,
                        st.search_term
                    FROM search_profiles sp
                    JOIN search_terms st
                        ON st.search_profile_id = sp.id
                    WHERE sp.profile_name = %s
                      AND sp.is_active = TRUE
                      AND st.is_active = TRUE
                    ORDER BY st.search_term;
                    """,
                    (profile_name,),
                )

                rows = cur.fetchall()

        return [
            (
                SearchProfile(
                    id=row[0],
                    profile_name=row[1],
                    source_name=row[2],
                    search_location=row[3],
                    search_radius_km=row[4],
                    offer_type=row[5],
                    page_size=row[6],
                ),
                SearchTerm(search_term=row[7]),
            )
            for row in rows
        ]

    def create_ingestion_run(
        self,
        source_name: str,
        search_profile_id: int,
        requested_url: str,
    ) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ingestion_runs (
                        source_name,
                        search_profile_id,
                        requested_url
                    )
                    VALUES (%s, %s, %s)
                    RETURNING id;
                    """,
                    (source_name, search_profile_id, requested_url),
                )
                return cur.fetchone()[0]

    def save_raw_job(
        self,
        record: RawJobRecord,
        ingestion_run_id: int,
        search_profile_id: int,
    ) -> int | None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO raw_jobs (
                        source_name,
                        source_url,
                        external_job_id,
                        raw_data,
                        ingestion_run_id,
                        search_profile_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_name, external_job_id)
                    WHERE external_job_id IS NOT NULL
                    DO NOTHING
                    RETURNING id;
                    """,
                    (
                        record.source_name,
                        record.source_url,
                        record.external_job_id,
                        json.dumps(record.raw_data, ensure_ascii=False),
                        ingestion_run_id,
                        search_profile_id,
                    ),
                )

                result = cur.fetchone()
                return None if result is None else result[0]

    def finish_ingestion_run(
        self,
        ingestion_run_id: int,
        total_loaded: int,
        inserted_count: int,
        duplicate_count: int,
    ) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ingestion_runs
                    SET
                        finished_at = NOW(),
                        status = 'success',
                        total_loaded = %s,
                        inserted_count = %s,
                        duplicate_count = %s
                    WHERE id = %s;
                    """,
                    (
                        total_loaded,
                        inserted_count,
                        duplicate_count,
                        ingestion_run_id,
                    ),
                )
