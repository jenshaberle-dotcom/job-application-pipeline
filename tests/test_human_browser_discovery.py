"""Offline browser discovery contract tests; no OpenAI, Brave or Playwright access."""
import json
from pathlib import Path

from src.search_intelligence.human_browser_discovery import (
    Company, Observation, matching_employer, valid_jobposting_for, verify_portal,
)

CATALOG = json.loads(Path("contracts/connector-capability-catalog-v1.json").read_text(
    encoding="utf-8"))


class Page:
    def __init__(self, url, status, body):
        self.url, self.status, self.body = url, status, body


def fake_provider(url):
    expected = "https://boards-api.greenhouse.io/v1/boards/acmesystems/jobs?content=true"
    if url != expected:
        raise OSError("unrecorded_http_url")
    return Page(url, 200, json.dumps({"jobs": [
        {"id": 723, "title": "Data Engineer", "content": "Build data pipelines in Python",
         "absolute_url": "https://boards.greenhouse.io/acmesystems/jobs/723",
         "location": {"name": "Hannover"}},
    ]}))


def company_observation():
    return Observation(
        "https://acme.example/", "ACME Systems GmbH – Karriere",
        "ACME Systems GmbH. Jobs bei uns.", (
            "https://boards.greenhouse.io/acmesystems/jobs/723",
        ), "<html><title>ACME Systems Karriere</title></html>")


def test_reachable_ats_with_job_does_not_autoverify_wrong_employer():
    company = Company("notacme", "Another Employer AG", "https://other.example/")
    result = verify_portal(company, "https://boards.greenhouse.io/acmesystems",
                           [company_observation()], fake_provider, CATALOG)
    assert result["status"] == "JOB_FOUND_EMPLOYER_CLAIM_UNCORROBORATED"
    assert result["factory_status"] == "NOT_ATTEMPTED"


def test_real_job_plus_exact_official_link_produces_factory_recipe():
    company = Company("acme", "ACME Systems GmbH", "https://acme.example/")
    result = verify_portal(company, "https://boards.greenhouse.io/acmesystems",
                           [company_observation()], fake_provider, CATALOG)
    assert result["status"] == "VERIFIED_ACTIVE"
    assert result["job_count"] == 1
    assert result["factory_status"] == "qualified_inactive"
    assert result["definition_status"] == "PASS"
    assert len(result["recipe_id"]) == 64
    assert result["runtime_admitted"] is False
    assert result["production_activated"] is False


def test_false_career_link_does_not_authorize_another_ats_tenant():
    company = Company("acme", "ACME Systems GmbH", "https://acme.example/")
    observation = company_observation()
    result = verify_portal(company, "https://boards.greenhouse.io/another",
                           [observation], lambda url: Page(url, 200, json.dumps({
                               "jobs": [{"id": 1, "title": "Developer",
                                         "content": "Cloud backend build and operations",
                                         "absolute_url":
                                         "https://boards.greenhouse.io/another/jobs/1",
                                         "location": {"name": "Hannover"}}]
                           })), CATALOG)
    assert result["status"] != "VERIFIED_ACTIVE"
    assert result["factory_status"] == "NOT_ATTEMPTED"


def test_zero_jobs_not_claimed_to_be_wrong_portal():
    company = Company("acme", "ACME Systems GmbH", "https://acme.example/")
    result = verify_portal(company, "https://boards.greenhouse.io/acmesystems",
                           [company_observation()],
                           lambda url: Page(url, 200, '{"jobs":[]}'), CATALOG)
    assert result["status"] == "SOURCE_VERIFIED_JOB_UNPROVEN"
    assert result["job_count"] == 0


def test_jobposting_requires_real_description_and_company():
    company = Company("acme", "ACME Systems GmbH", "https://acme.example/")
    html = """<script type="application/ld+json">
    {"@type":"JobPosting","title":"Solution Architect",
     "description":"Design application architectures with teams and platforms.",
     "url":"https://jobs.example.com/position/42",
     "hiringOrganization":{"name":"ACME Systems GmbH",
                           "sameAs":"https://acme.example/"}}</script>"""
    observation = Observation("https://jobs.example.com/position/42",
                              "Job", "Apply", (), html)
    results = valid_jobposting_for(company, observation)
    assert results[0]["title"] == "Solution Architect"
    verified = verify_portal(company, observation.url, [observation],
                             lambda url: (_ for _ in ()).throw(OSError()),
                             CATALOG)
    assert verified["status"] == "VERIFIED_ACTIVE"
    assert verified["factory_status"] == "UNSUPPORTED_PROVIDER"


def test_self_declared_employer_without_independent_site_evidence_is_not_verified():
    company = Company("acme", "ACME Systems GmbH")
    html = """<script type="application/ld+json">
    {"@type":"JobPosting","title":"Solution Architect",
     "description":"Design application architectures with teams and platforms.",
     "url":"https://jobs.example.com/position/42",
     "hiringOrganization":{"name":"ACME Systems GmbH"}}</script>"""
    observation = Observation("https://jobs.example.com/position/42",
                              "Job", "Apply", (), html)
    verified = verify_portal(company, observation.url, [observation],
                             lambda url: (_ for _ in ()).throw(OSError()),
                             CATALOG)
    assert verified["status"] == "JOB_FOUND_EMPLOYER_CLAIM_UNCORROBORATED"


def test_legal_name_normalization_excludes_unrelated_titles():
    assert matching_employer("ACME Systems GmbH", "ACME Systems") is True
    assert matching_employer("ACME Systems GmbH", "Other Systems AG") is False


def test_baseline_csv_only_accepts_explicit_company_truth(tmp_path):
    import pytest
    from scripts.run_hannover_browser_agent import read_baseline
    path = tmp_path / "baseline.csv"
    path.write_text("company_key,verified_active\nacme,1\nbeta,false\n",
                    encoding="utf-8")
    assert read_baseline(str(path)) == {"acme": True, "beta": False}
    path.write_text("company_key,verified_active\nacme,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="requires_company_key"):
        read_baseline(str(path))


def test_browser_only_allows_observed_public_https_url_shape_without_dns():
    import pytest
    from scripts.run_hannover_browser_agent import require_public_https
    assert require_public_https("https://jobs.example.org/123", resolve_dns=False)
    with pytest.raises(ValueError):
        require_public_https("http://jobs.example.org")
    with pytest.raises(ValueError):
        require_public_https("https://127.0.0.1/private", resolve_dns=False)
