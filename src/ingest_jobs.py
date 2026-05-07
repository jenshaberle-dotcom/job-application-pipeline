import json
import os

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

SOURCE_NAME = "bundesagentur_fuer_arbeit"
PROFILE_NAME = "ba_data_engineer_30629_50km"
BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"


def get_connection():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                sp.id,
                sp.profile_name,
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
            (PROFILE_NAME,),
        )

        search_terms = cur.fetchall()

        if not search_terms:
            raise ValueError(f"No active search terms found for profile: {PROFILE_NAME}")

        total_loaded_all = 0
        inserted_count_all = 0
        duplicate_count_all = 0

        for (
            search_profile_id,
            profile_name,
            search_location,
            search_radius_km,
            offer_type,
            page_size,
            search_term,
        ) in search_terms:
            search_params = {
                "was": search_term,
                "wo": search_location,
                "umkreis": search_radius_km,
                "page": 1,
                "size": page_size,
                "angebotsart": offer_type,
            }

            headers = {
                "X-API-Key": os.getenv("BA_API_KEY", "jobboerse-jobsuche"),
            }

            response = requests.get(
                BASE_URL,
                params=search_params,
                headers=headers,
                timeout=30,
            )

            print("---")
            print(f"Profile: {profile_name}")
            print(f"Search term: {search_term}")
            print("Status Code:", response.status_code)
            print("Final URL:", response.url)

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
                (
                    SOURCE_NAME,
                    search_profile_id,
                    response.url,
                ),
            )

            ingestion_run_id = cur.fetchone()[0]

            response.raise_for_status()

            data = response.json()
            jobs = data.get("stellenangebote", [])

            print(f"{len(jobs)} Jobs geladen")

            inserted_count = 0
            duplicate_count = 0

            for job in jobs:
                source_url = (
                    job.get("externeUrl")
                    or job.get("url")
                    or f"ba://{job.get('refnr')}"
                )

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
                        SOURCE_NAME,
                        source_url,
                        job.get("refnr"),
                        json.dumps(
                            {
                                "search_profile": {
                                    "profile_name": profile_name,
                                    "search_term": search_term,
                                    "search_location": search_location,
                                    "search_radius_km": search_radius_km,
                                    "offer_type": offer_type,
                                    "page_size": page_size,
                                },
                                "job": job,
                            },
                            ensure_ascii=False,
                        ),
                        ingestion_run_id,
                        search_profile_id,
                    ),
                )

                result = cur.fetchone()

                if result is None:
                    duplicate_count += 1
                    print(
                        f"Bereits vorhanden: {job.get('titel')} | "
                        f"{job.get('arbeitgeber')}"
                    )
                    continue

                new_id = result[0]
                inserted_count += 1

                print(
                    f"Gespeichert: ID={new_id} | "
                    f"{job.get('titel')} | "
                    f"{job.get('arbeitgeber')}"
                )

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
                    len(jobs),
                    inserted_count,
                    duplicate_count,
                    ingestion_run_id,
                ),
            )

            total_loaded_all += len(jobs)
            inserted_count_all += inserted_count
            duplicate_count_all += duplicate_count

            print(f"Ingestion Run ID: {ingestion_run_id}")
            print(f"Neue Jobs gespeichert: {inserted_count}")
            print(f"Bereits vorhandene Jobs übersprungen: {duplicate_count}")

        print("===")
        print(f"Gesamt geladen: {total_loaded_all}")
        print(f"Gesamt neu gespeichert: {inserted_count_all}")
        print(f"Gesamt bereits vorhanden: {duplicate_count_all}")
