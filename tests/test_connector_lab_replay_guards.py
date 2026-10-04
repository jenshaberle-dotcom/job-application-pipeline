import json
import subprocess
from pathlib import Path

import pytest

from scripts.run_multi_region_company_discovery import run
from scripts.materialize_connector_ml_corpus import materialize
from src.search_intelligence.connector_mass_census import build_mass_census, seeds_from_payload
from src.search_intelligence.discovery_coverage import assess
from src.search_intelligence.public_directory_discovery import DirectorySource, seed


def test_directory_profiles_do_not_collapse_to_one_directory_domain():
    source = DirectorySource("directory", "BERLIN", ("TECH",), "https://directory.example/list")
    payload = [
        seed(name, source, directory_url=f"https://directory.example/{name}")
        for name in ("Acme", "Other")
    ]
    census = build_mass_census(seeds_from_payload(payload, default_source="directory"))
    assert len(census["candidates"]) == 2
    assert all(not row["websites"] for row in census["candidates"])
    assert all(row["directory_urls"] for row in census["candidates"])


def test_memberships_survive_input_without_social_leaking_to_berlin():
    rows = [
        {
            "name": "Acme",
            "website": "acme.example",
            "geography": "REGION_HANNOVER",
            "cohorts": ["TECH", "SOCIAL"],
        },
        {"name": "Acme", "website": "acme.example", "geography": "BERLIN", "cohorts": ["TECH"]},
    ]
    census = build_mass_census(seeds_from_payload(rows, default_source="directory"))
    coverage = assess(census)
    assert census["candidates"][0]["cohorts"] == ["SOCIAL", "TECH"]
    assert coverage["geography_cohort_counts"]["BERLIN"]["SOCIAL"] == 0
    assert coverage["geography_cohort_counts"]["REGION_HANNOVER"]["SOCIAL"] == 1


def test_failed_source_does_not_stop_other_sources_or_reuse_stale_snapshot(tmp_path):
    stale = tmp_path / "hochschule_hannover_career_center.json"
    stale.write_text(json.dumps({"companies": [{"name": "Stale"}]}))
    calls = []

    def execute(command, **kwargs):
        calls.append(command)
        if command[2] == "scripts.discover_hannover_tech_hsh":
            raise subprocess.CalledProcessError(1, command)
        target = Path(command[-1])
        target.write_text(
            json.dumps(
                {
                    "source_id": target.stem,
                    "companies": [
                        {"name": target.stem, "geography": "BERLIN", "cohorts": ["TECH"]}
                    ],
                }
            )
        )

    census_path = run(tmp_path, execute=execute)
    coverage = json.loads((tmp_path / "discovery-coverage.json").read_text())
    assert len(calls) == 6
    assert not stale.exists()
    assert len(json.loads(census_path.read_text())["candidates"]) == 5
    assert coverage["sources"][0]["status"] == "SOURCE_DISCOVERY_FAILURE"
    assert coverage["factory_run_recommended"]
    assert not coverage["ml_scale_ready"]


def test_all_source_failures_leave_report_and_no_stale_census(tmp_path):
    (tmp_path / "multi-region-company-census.json").write_text("{}")

    def execute(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 1)

    with pytest.raises(RuntimeError, match="no_usable_company_population"):
        run(tmp_path, execute=execute)
    assert (tmp_path / "discovery-coverage.json").exists()
    assert not (tmp_path / "multi-region-company-census.json").exists()


@pytest.mark.parametrize(
    "jobs,complete,expected",
    [(0, True, "ZERO_JOB_VALID_SOURCE"), (2, True, "SUCCESS"), (2, False, "RUNTIME_GAP")],
)
def test_ml_success_requires_complete_runtime_and_qualification(jobs, complete, expected):
    census = {
        "population_digest": "a" * 64,
        "candidates": [
            {
                "company_key": "acme",
                "geographies": ["BERLIN"],
                "cohorts": ["TECH"],
                "seed_sources": ["directory"],
            }
        ],
    }
    row = {
        "company_key": "acme",
        "factory_disposition": "qualified_inactive",
        "origin_verified": True,
        "runtime_admitted": True,
        "qualification_status": "PASS",
        "extraction": {
            "status": "PASS",
            "complete": complete,
            "job_count": jobs,
            "field_presence": {"title": True},
        },
    }
    example = materialize(census, {"candidates": [row]})["examples"][0]
    assert example["label"] == expected
    assert example["job_count"] == jobs
    assert example["extraction_field_presence"] == {"title": True}


def test_matching_name_bridges_domain_evidence_only_when_unambiguous():
    rows = [
        {"name": "Acme GmbH", "geography": "BERLIN"},
        {"name": "Acme", "website": "acme.example", "geography": "MUNICH"},
    ]
    census = build_mass_census(seeds_from_payload(rows, default_source="directory"))
    assert len(census["candidates"]) == 1
    assert census["candidates"][0]["geographies"] == ["BERLIN", "MUNICH"]
    rows.append({"name": "Acme", "website": "another.example"})
    assert (
        len(build_mass_census(seeds_from_payload(rows, default_source="directory"))["candidates"])
        == 3
    )


def test_social_only_does_not_satisfy_tech_minimum():
    result = assess(
        {"candidates": [{"geographies": ["REGION_HANNOVER"], "cohorts": ["SOCIAL"]}] * 250}
    )
    assert result["coverage_gaps"]["REGION_HANNOVER"]["actual"] == 0


def test_ml_incomplete_population_cannot_silently_drop_failures():
    census = {"population_digest": "a" * 64, "candidates": [{"company_key": "acme"}]}
    with pytest.raises(ValueError, match="evaluation_population_mismatch"):
        materialize(census, {"candidates": []})


def test_configured_pagination_stops_when_server_repeats_page(monkeypatch):
    from scripts import discover_configured_directory as module

    calls = []

    def fetch(url):
        calls.append(url)
        return '<a href="/companies/acme">Acme</a>'

    monkeypatch.setattr(module, "fetch_text", fetch)
    result = module.discover(
        {
            "source_id": "test",
            "geography": "BERLIN",
            "start_url": "https://directory.example/list",
            "page_url_template": "https://directory.example/list?page={page}",
            "include_href": ["/companies/"],
            "delay_seconds": 0,
            "max_pages": 100,
        }
    )
    assert result["company_count"] == 1
    assert len(calls) == 3
