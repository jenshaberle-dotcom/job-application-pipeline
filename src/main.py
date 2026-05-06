import json
import psycopg

test_job = {
    "title": "Data Engineer",
    "company": "Test Company",
    "location": "Hannover",
    "description": "Erster Testdatensatz für unsere Job-Pipeline",
    "skills": ["Python", "SQL", "PostgreSQL"]
}

conn = psycopg.connect(
    host="localhost",
    port=5432,
    dbname="job_pipeline",
    user="job_user",
    password="job_password"
)

cur = conn.cursor()

cur.execute(
    """
    INSERT INTO raw_jobs (source_name, source_url, raw_data)
    VALUES (%s, %s, %s)
    RETURNING id;
    """,
    (
        "manual_test",
        "https://example.com/jobs/data-engineer-1",
        json.dumps(test_job)
    )
)

new_id = cur.fetchone()[0]
conn.commit()

print(f"Job gespeichert mit ID: {new_id}")

cur.close()
conn.close()
