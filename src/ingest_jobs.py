import json
import os

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"

SEARCH_PROFILE = {
    "was": "Data Engineer",
    "wo": "30629",
    "umkreis": 50,
    "page": 1,
    "size": 10,
    "angebotsart": 1,
}

headers = {
    "X-API-Key": os.getenv("BA_API_KEY", "jobboerse-jobsuche"),
}

response = requests.get(
    BASE_URL,
    params=SEARCH_PROFILE,
    headers=headers,
    timeout=30,
)

print("Status Code:", response.status_code)
print("Final URL:", response.url)

response.raise_for_status()

data = response.json()
jobs = data.get("stellenangebote", [])

print(f"{len(jobs)} Jobs geladen")

conn = psycopg.connect(
    host=os.getenv("POSTGRES_HOST"),
    port=int(os.getenv("POSTGRES_PORT", "5432")),
    dbname=os.getenv("POSTGRES_DB"),
    user=os.getenv("POSTGRES_USER"),
    password=os.getenv("POSTGRES_PASSWORD"),
)

cur = conn.cursor()

inserted_count = 0
duplicate_count = 0

for job in jobs:
    source_url = job.get("externeUrl") or job.get("url") or f"ba://{job.get('refnr')}"

    cur.execute(
        """
        INSERT INTO raw_jobs (
            source_name,
            source_url,
            external_job_id,
            raw_data
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (source_name, external_job_id)
        WHERE external_job_id IS NOT NULL
        DO NOTHING
        RETURNING id;
        """,
        (
            "bundesagentur_fuer_arbeit",
            source_url,
            job.get("refnr"),
            json.dumps(
                {
                    "search_profile": SEARCH_PROFILE,
                    "job": job,
                },
                ensure_ascii=False,
            ),
        ),
    )

    result = cur.fetchone()

    if result is None:
        duplicate_count += 1
        print(f"Bereits vorhanden: {job.get('titel')} | {job.get('arbeitgeber')}")
        continue

    new_id = result[0]
    inserted_count += 1

    print(f"Gespeichert: ID={new_id} | {job.get('titel')} | {job.get('arbeitgeber')}")

conn.commit()

print("---")
print(f"Neue Jobs gespeichert: {inserted_count}")
print(f"Bereits vorhandene Jobs übersprungen: {duplicate_count}")

cur.close()
conn.close()
