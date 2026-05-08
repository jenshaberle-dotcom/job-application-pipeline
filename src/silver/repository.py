import psycopg
from psycopg.rows import dict_row

from src.config import get_database_config


class SilverJobRepository:
    def __init__(self) -> None:
        self.connection_config = get_database_config()

    def get_connection(self):
        return psycopg.connect(**self.connection_config, row_factory=dict_row)

    def load_unprocessed_raw_jobs(self, limit: int = 100) -> list[dict]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        r.id,
                        r.source_name,
                        r.external_job_id,
                        r.source_url,
                        r.raw_data
                    FROM raw_jobs r
                    LEFT JOIN silver_jobs s
                        ON s.raw_job_id = r.id
                    WHERE s.id IS NULL
                        AND r.source_name = 'bundesagentur_fuer_arbeit'
                    ORDER BY r.id
                    LIMIT %s;
                    """,
                    (limit,),
                )
                return list(cur.fetchall())

    def upsert_silver_job(self, job: dict) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO silver_jobs (
                        raw_job_id,
                        source_name,
                        external_job_id,
                        source_url,
                        title,
                        company_name,
                        city,
                        postal_code,
                        country,
                        publication_date
                    )
                    VALUES (
                        %(raw_job_id)s,
                        %(source_name)s,
                        %(external_job_id)s,
                        %(source_url)s,
                        %(title)s,
                        %(company_name)s,
                        %(city)s,
                        %(postal_code)s,
                        %(country)s,
                        %(publication_date)s
                    )
                    ON CONFLICT (raw_job_id)
                    DO UPDATE SET
                        source_name = EXCLUDED.source_name,
                        external_job_id = EXCLUDED.external_job_id,
                        source_url = EXCLUDED.source_url,
                        title = EXCLUDED.title,
                        company_name = EXCLUDED.company_name,
                        city = EXCLUDED.city,
                        postal_code = EXCLUDED.postal_code,
                        country = EXCLUDED.country,
                        publication_date = EXCLUDED.publication_date,
                        normalized_at = NOW(),
                        updated_at = NOW();
                    """,
                    job,
                )
