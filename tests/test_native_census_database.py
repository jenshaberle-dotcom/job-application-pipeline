"""Integration against session-local PostgreSQL tables; never production tables."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import psycopg
import pytest

from scripts import run_native_census_campaign as worker


@pytest.fixture
def database():
    config = os.environ.get("RCC_TEST_DATABASE_CONFIG")
    if not config:
        pytest.skip("Explicit local PostgreSQL test connection required")
    with psycopg.connect(**json.loads(Path(config).read_bytes()), autocommit=True) as db:
        db.execute("SET search_path = pg_temp")
        sql = (worker.ROOT / "db/migrations/118_create_native_census_campaign.sql").read_text()
        db.execute(sql.replace("CREATE TABLE IF NOT EXISTS", "CREATE TEMP TABLE"))
        db.execute("""CREATE TEMP TABLE employer_origin_source_candidates
                      (id bigint, company_key text,company_name text,candidate_url text,updated_at timestamptz)""")
        db.execute("INSERT INTO employer_origin_source_candidates VALUES (1,'existing','Existing','https://existing.example',now())")
        yield db


def test_full_population_raw_evidence_batches_and_no_replay(database, tmp_path, monkeypatch):
    db = database
    def crawl(command, **kwargs):
        source = command[2].split(".")[-1]
        target = Path(command[-1])
        rows = [{"company_name": f"{source}-{target.stem}-{n}", "website": "https://example.org"}
                for n in range(31)]
        target.write_text(json.dumps({"companies": rows, "complete": True}))
        evidence = Path(kwargs["env"]["JAP_CENSUS_EVIDENCE_DIR"])
        raw = b"original public response"
        (evidence / "response.body").write_bytes(raw)
        (evidence / "response.json").write_text(json.dumps(
            {"url": "https://example.org", "sha256": hashlib.sha256(raw).hexdigest()}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker.subprocess, "run", crawl)
    proof = worker.collect(db, "test-run", "a" * 40, tmp_path)
    assert proof["status"] == "BRONZE_READY"
    assert proof["candidate_count"] == 187
    assert proof["factory_batch_count"] == 2
    assert db.execute("SELECT count(*) FROM bronze_native_census_http").fetchone()[0] == 6
    with pytest.raises(psycopg.errors.UniqueViolation):
        worker.collect(db, "test-run", "a" * 40, tmp_path)
    calls = []
    def assess(command, **kwargs):
        row = json.loads(Path(command[-3]).read_text())
        calls.append(row["id"])
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(command, 45)
        Path(command[-1]).write_text(json.dumps({
            "candidate_id": row["id"], "company_key": row["company_key"], "recipe_ready": True}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(worker.subprocess, "run", assess)
    batches = []
    for index in range(2):
        directory = tmp_path / str(index)
        directory.mkdir()
        batches.append(worker.factory_batch(db, "test-run", index, directory))
        # Reading completed outcomes must not run a single candidate again.
        assert worker.factory_batch(db, "test-run", index, directory) == batches[-1]
    assert len(calls) == 187
    assert sum(b["candidates"] for b in batches) == 187
    assert sum(b["outcomes"].get("TIME_LIMIT", 0) for b in batches) == 1
    assert db.execute("SELECT count(*) FROM employer_origin_source_candidates").fetchone()[0] == 1


def test_uncertain_candidate_is_not_replayed(database, tmp_path, monkeypatch):
    db = database
    db.execute("""INSERT INTO bronze_native_census_runs(run_id,source_sha,state,summary)
                  VALUES ('r','a','BRONZE_READY','{"factory_batch_count":1}')""")
    identity = db.execute("""INSERT INTO bronze_native_census_candidates(run_id,company_key,observation,batch_index)
                            VALUES ('r','c','{"company_name":"C","company_key":"c","websites":[]}',0)
                            RETURNING id""").fetchone()[0]
    db.execute("INSERT INTO native_census_factory_results(candidate_id,state,result) VALUES (%s,'ASSESSING','{}')",
               (identity,))
    monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: pytest.fail("Unexpected replay"))
    with pytest.raises(RuntimeError, match="RECONCILIATION"):
        worker.factory_batch(db, "r", 0, tmp_path)


def test_failed_sources_do_not_claim_complete_census(database, tmp_path, monkeypatch):
    monkeypatch.setattr(worker.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    proof = worker.collect(database, "failure", "b" * 40, tmp_path)
    assert proof["status"] == "REVIEW_REQUIRED"
    assert proof["candidate_count"] == 1  # Existing Classic candidate retained.
    assert set(proof["sources"].values()) == {"SOURCE_FAILED"}
