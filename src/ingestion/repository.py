import json
import psycopg

from src.config import get_database_config
from src.connectors.base import RawJobRecord, SearchProfile, SearchTerm
from src.normalization.company_keys import normalize_company_key


class JobIngestionRepository:
    def __init__(self) -> None:
        self.connection_config = get_database_config()

    def get_connection(self):
        return psycopg.connect(**self.connection_config)

    def load_search_profile(
        self,
        profile_name: str,
    ) -> SearchProfile:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        profile_name,
                        source_name,
                        search_location,
                        search_radius_km,
                        offer_type,
                        page_size
                    FROM search_profiles
                    WHERE profile_name = %s
                      AND is_active = TRUE;
                    """,
                    (profile_name,),
                )

                row = cur.fetchone()

        if row is None:
            raise ValueError(f"No active search profile found: {profile_name}")

        return SearchProfile(
            id=row[0],
            profile_name=row[1],
            source_name=row[2],
            search_location=row[3],
            search_radius_km=row[4],
            offer_type=row[5],
            page_size=row[6],
        )

    def load_active_search_profiles(self) -> list[SearchProfile]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        profile_name,
                        source_name,
                        search_location,
                        search_radius_km,
                        offer_type,
                        page_size
                    FROM search_profiles
                    WHERE is_active = TRUE
                    ORDER BY source_name, profile_name;
                    """
                )

                rows = cur.fetchall()

        return [
            SearchProfile(
                id=row[0],
                profile_name=row[1],
                source_name=row[2],
                search_location=row[3],
                search_radius_km=row[4],
                offer_type=row[5],
                page_size=row[6],
            )
            for row in rows
        ]

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
                        st.id,
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
                SearchTerm(
                    id=row[7],
                    search_term=row[8],
                ),
            )
            for row in rows
        ]

    def load_employer_origin_candidate_company_keys(self) -> set[str]:
        """Load DB-backed employer-origin company keys for aggregator suppression.

        Aggregator discovery sources such as StepStone should not repeatedly spend
        their bounded result-card budget on employers that are already known as
        employer-origin candidates. This method returns raw company identifiers;
        normalization is intentionally performed in the ingestion filter so tests
        and non-DB call sites can use the same policy.
        """

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT company_key, company_name, source_family_candidate
                    FROM employer_origin_source_candidates
                    ORDER BY company_key, id;
                    """
                )

                rows = cur.fetchall()

        values: set[str] = set()
        for row in rows:
            for value in row:
                if value is not None and str(value).strip():
                    values.add(str(value))

        return values

    def load_aggregator_discovery_suppression_company_keys(self) -> set[str]:
        """Load company keys that should be suppressed from bounded aggregator discovery.

        S5A makes suppression lifecycle-aware: active controlled and hard-stop
        candidates can be suppressed from StepStone persistence, but unresolved
        candidates such as manual_review_required must remain observable as market
        evidence so false-negative risk can be detected.
        """

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT company_key, company_name, source_family_candidate
                    FROM employer_origin_source_candidates
                    WHERE status IN (
                        'active_controlled',
                        'deprecated',
                        'disabled',
                        'abort_documented',
                        'not_actionable'
                    )
                    ORDER BY company_key, id;
                    """
                )

                rows = cur.fetchall()

        values: set[str] = set()
        for row in rows:
            for value in row:
                if value is not None and str(value).strip():
                    values.add(str(value))

        return values

    def save_market_evidence(
        self,
        *,
        evidence_source: str,
        evidence_kind: str,
        source_name: str,
        company_name: str,
        title: str,
        evidence_url: str | None,
        search_profile_name: str | None = None,
        search_term: str | None = None,
        ingestion_run_id: int | None = None,
        raw_job_external_id: str | None = None,
        evidence: dict | None = None,
    ) -> int | None:
        normalized_company_key = normalize_company_key(company_name)
        if not normalized_company_key or not title.strip():
            return None

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO market_evidence (
                        evidence_source,
                        evidence_kind,
                        source_name,
                        normalized_company_key,
                        company_name,
                        title,
                        evidence_url,
                        search_profile_name,
                        search_term,
                        ingestion_run_id,
                        raw_job_external_id,
                        evidence
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s::jsonb
                    )
                    ON CONFLICT DO NOTHING
                    RETURNING id;
                    """,
                    (
                        evidence_source,
                        evidence_kind,
                        source_name,
                        normalized_company_key,
                        company_name,
                        title,
                        evidence_url,
                        search_profile_name,
                        search_term,
                        ingestion_run_id,
                        raw_job_external_id,
                        json.dumps(evidence or {}, ensure_ascii=False),
                    ),
                )
                result = cur.fetchone()
                return None if result is None else result[0]

    def create_ingestion_run(
        self,
        source_name: str,
        search_profile_id: int,
        search_term_id: int | None = None,
        search_term: str | None = None,
        requested_url: str | None = None,
    ) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ingestion_runs (
                        source_name,
                        search_profile_id,
                        search_term_id,
                        search_term,
                        requested_url
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id;
                    """,
                    (
                        source_name,
                        search_profile_id,
                        search_term_id,
                        search_term,
                        requested_url,
                    ),
                )
                return cur.fetchone()[0]

    def update_ingestion_run_requested_url(
        self,
        ingestion_run_id: int,
        requested_url: str,
    ) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ingestion_runs
                    SET requested_url = %s
                    WHERE id = %s;
                    """,
                    (
                        requested_url,
                        ingestion_run_id,
                    ),
                )

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

    def find_existing_raw_job_id(
        self,
        source_name: str,
        external_job_id: str | None,
    ) -> int | None:
        if external_job_id is None:
            return None

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM raw_jobs
                    WHERE source_name = %s
                      AND external_job_id = %s;
                    """,
                    (
                        source_name,
                        external_job_id,
                    ),
                )

                result = cur.fetchone()

        return None if result is None else result[0]

    def save_job_observation(
        self,
        record: RawJobRecord,
        ingestion_run_id: int,
        raw_job_id: int | None,
    ) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO job_observations (
                        source_name,
                        external_job_id,
                        source_url,
                        ingestion_run_id,
                        raw_job_id,
                        is_seen
                    )
                    VALUES (%s, %s, %s, %s, %s, TRUE)
                    ON CONFLICT (
                        ingestion_run_id,
                        source_name,
                        external_job_id
                    )
                    WHERE external_job_id IS NOT NULL
                    DO UPDATE SET
                        source_url = EXCLUDED.source_url,
                        raw_job_id = COALESCE(
                            job_observations.raw_job_id,
                            EXCLUDED.raw_job_id
                        ),
                        is_seen = TRUE;
                    """,
                    (
                        record.source_name,
                        record.external_job_id,
                        record.source_url,
                        ingestion_run_id,
                        raw_job_id,
                    ),
                )

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

    def fail_ingestion_run(
        self,
        ingestion_run_id: int,
        error_message: str,
        error_type: str | None = None,
        error_stage: str | None = None,
    ) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE ingestion_runs
                    SET
                        finished_at = NOW(),
                        status = 'failed',
                        error_type = %s,
                        error_stage = %s,
                        error_message = %s
                    WHERE id = %s;
                    """,
                    (
                        error_type,
                        error_stage,
                        error_message,
                        ingestion_run_id,
                    ),
                )
