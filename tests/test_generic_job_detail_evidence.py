from __future__ import annotations

import json

from src.connectors.generic_job_detail_evidence import (
    EVIDENCE_SCHEMA,
    GENERIC_LOCATION_EVIDENCE_SOURCE,
    MAX_REQUIREMENT_TEXT_CHARS,
    extract_generic_job_detail_evidence,
    project_detail_evidence_into_raw_data,
)


def test_extracts_schema_org_jobposting_without_portal_knowledge() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Data Platform Engineer",
        "description": "<p>Build reliable data platforms with Python and SQL.</p>",
        "hiringOrganization": {"@type": "Organization", "name": "Example GmbH"},
        "jobLocation": {
          "@type": "Place",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Hannover",
            "addressRegion": "Niedersachsen",
            "postalCode": "30159",
            "addressCountry": "DE"
          }
        },
        "jobLocationType": "TELECOMMUTE",
        "applicantLocationRequirements": {"@type": "Country", "name": "Germany"},
        "employmentType": ["FULL_TIME"],
        "skills": ["Python", "SQL"],
        "datePosted": "2026-09-01",
        "identifier": "REQ-123"
      }
      </script>
    </head><body><h1>Data Platform Engineer</h1></body></html>
    """

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://jobs.example.com/job/12345",
        page_title="Example career page",
    )

    assert evidence["schema"] == EVIDENCE_SCHEMA
    assert evidence["structured_jobposting_found"] is True
    assert evidence["structured_source"] == "json-ld"
    assert evidence["parser_family"] == "schema_org_json_ld"
    assert evidence["title"] == "Data Platform Engineer"
    assert evidence["company_name"] == "Example GmbH"
    assert "Hannover" in " ".join(evidence["locations"])
    assert evidence["structured_locations"] == [
        {
            "city": "Hannover",
            "country_code": "DE",
            "evidence_source": GENERIC_LOCATION_EVIDENCE_SOURCE,
            "evidence_text": "Hannover | Niedersachsen | 30159 | DE",
        }
    ]
    assert evidence["applicant_locations"] == ["Germany"]
    assert evidence["remote"] is True
    assert evidence["employment_types"] == ["FULL_TIME"]
    assert evidence["skills"] == ["Python", "SQL"]
    assert evidence["identifier"] == "REQ-123"
    assert evidence["vacancy_identity_kind"] == "structured_identifier"
    assert evidence["field_presence"]["locations"] is True
    assert evidence["field_presence"]["identifier"] is True
    assert evidence["raw_html_persisted"] is False


def test_structured_requirement_text_preserves_late_description_evidence_beyond_4k() -> None:
    prefix = "Platform engineering context without requirement signal. " * 140
    late_signal = "Sehr gute Deutschkenntnisse auf C1-Niveau."
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Data Platform Engineer",
        "description": f"<p>{prefix}{late_signal}</p>",
    }
    html = (
        '<html><head><script type="application/ld+json">'
        + json.dumps(posting, ensure_ascii=False)
        + "</script></head><body><h1>Data Platform Engineer</h1></body></html>"
    )

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://jobs.example.com/job/late-requirement",
    )

    assert len(evidence["description_excerpt"]) <= 4_000
    assert late_signal not in evidence["description_excerpt"]
    assert late_signal in evidence["requirement_text_excerpt"]
    assert len(evidence["requirement_text_excerpt"]) <= MAX_REQUIREMENT_TEXT_CHARS
    assert evidence["requirement_text_source"] == "json-ld"
    assert evidence["raw_html_persisted"] is False

    projected = project_detail_evidence_into_raw_data({"job": {}}, evidence)
    assert projected["job"]["requirement_text"] == evidence["requirement_text_excerpt"]
    assert projected["job"]["metadata"]["requirement_text_source"] == "json-ld"


def test_explicit_structured_requirements_are_prioritized_before_long_description() -> None:
    posting = {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Machine Learning Engineer",
        "description": "Role context. " * 1_500,
        "qualifications": "Fluent German and English. 38 hours per week.",
        "skills": ["Python", "Kubernetes"],
    }
    html = (
        '<html><head><script type="application/ld+json">'
        + json.dumps(posting)
        + "</script></head><body></body></html>"
    )

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://jobs.example.com/job/structured-requirements",
    )

    requirement_text = evidence["requirement_text_excerpt"]
    assert requirement_text.startswith("Fluent German and English. 38 hours per week.")
    assert "Skills: Python; Kubernetes" in requirement_text
    assert len(requirement_text) <= MAX_REQUIREMENT_TEXT_CHARS


def test_extracts_microdata_jobposting() -> None:
    html = """
    <html><body itemscope itemtype="https://schema.org/JobPosting">
      <h1 itemprop="title">Machine Learning Engineer</h1>
      <div itemprop="hiringOrganization" itemscope itemtype="https://schema.org/Organization">
        <span itemprop="name">Neutral Employer AG</span>
      </div>
      <div itemprop="jobLocation" itemscope itemtype="https://schema.org/Place">
        <div itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">
          <span itemprop="addressLocality">Hannover</span>
          <span itemprop="addressCountry">DE</span>
        </div>
      </div>
      <div itemprop="description">Python machine learning platform work.</div>
    </body></html>
    """

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://career.neutral.invalid/jobs/ml-42",
    )

    assert evidence["structured_jobposting_found"] is True
    assert evidence["structured_source"] == "microdata"
    assert evidence["parser_family"] == "schema_org_microdata"
    assert evidence["title"] == "Machine Learning Engineer"
    assert evidence["company_name"] == "Neutral Employer AG"
    assert "Hannover" in " ".join(evidence["locations"])


def test_trafilatura_fallback_is_bounded_and_does_not_persist_html() -> None:
    repeated = "Python SQL data engineering observability remote Germany. " * 200
    html = f"""
    <html><head><title>Platform Engineer</title></head>
    <body><main><h1>Platform Engineer</h1><p>{repeated}</p></main></body></html>
    """

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://jobs.example.org/vacancy/98765",
        page_title="Platform Engineer",
    )

    assert evidence["structured_jobposting_found"] is False
    assert evidence["parser_family"] == "generic_dom_text"
    assert "trafilatura:main_text" in evidence["methods"]
    assert evidence["description_excerpt"]
    assert len(evidence["description_excerpt"]) <= 4_000
    assert evidence["requirement_text_excerpt"]
    assert len(evidence["requirement_text_excerpt"]) <= MAX_REQUIREMENT_TEXT_CHARS
    assert evidence["vacancy_identity_kind"] == "source_url"
    assert evidence["raw_html_persisted"] is False
    assert "<html" not in evidence["description_excerpt"].casefold()
    assert "<html" not in evidence["requirement_text_excerpt"].casefold()


def test_projection_enriches_existing_raw_shape_without_source_special_case() -> None:
    raw_data = {
        "source_type": "employer_origin_career_site",
        "job": {
            "title": "Old page title",
            "company_name": "Example GmbH",
            "source_url": "https://jobs.example.com/job/12345",
        },
        "result_card": {
            "title": "Old page title",
            "company_name": "Example GmbH",
            "detail_url": "https://jobs.example.com/job/12345",
        },
    }
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "methods": ["extruct:json-ld"],
        "parser_family": "schema_org_json_ld",
        "field_presence": {
            "title": True,
            "requirement_text": True,
            "locations": True,
            "identifier": True,
        },
        "structured_jobposting_found": True,
        "structured_source": "json-ld",
        "title": "Data Engineer",
        "company_name": "Example GmbH",
        "description_excerpt": "Python SQL data platform",
        "description_source": "json-ld",
        "requirement_text_excerpt": "Fluent German. Python SQL data platform",
        "requirement_text_source": "json-ld",
        "locations": ["Hannover | Niedersachsen | DE"],
        "structured_locations": [
            {
                "city": "Hannover",
                "country_code": "DE",
                "evidence_source": GENERIC_LOCATION_EVIDENCE_SOURCE,
                "evidence_text": "Hannover | Niedersachsen | DE",
            }
        ],
        "applicant_locations": ["Germany"],
        "remote": True,
        "employment_types": ["FULL_TIME"],
        "skills": ["Python", "SQL"],
        "date_posted": "2026-09-01",
        "valid_through": None,
        "identifier": "REQ-42",
        "vacancy_identity_kind": "structured_identifier",
        "raw_html_persisted": False,
    }

    projected = project_detail_evidence_into_raw_data(raw_data, evidence)

    assert projected["job"]["title"] == "Data Engineer"
    assert projected["job"]["description"] == "Python SQL data platform"
    assert projected["job"]["requirement_text"] == "Fluent German. Python SQL data platform"
    assert projected["job"]["location"] == "Hannover | Niedersachsen | DE"
    assert projected["job"]["locations"][0]["city"] == "Hannover"
    assert projected["job"]["skills"] == ["Python", "SQL"]
    assert projected["job"]["metadata"]["workplace_type"] == "remote"
    assert projected["job"]["metadata"]["structured_identifier"] == "REQ-42"
    assert projected["job"]["metadata"]["parser_family"] == "schema_org_json_ld"
    assert projected["job"]["metadata"]["vacancy_identity_kind"] == "structured_identifier"
    assert projected["job"]["metadata"]["requirement_text_source"] == "json-ld"
    assert projected["job"]["metadata"]["structure_field_presence"]["locations"] is True
    assert projected["detail_evidence"]["raw_html_persisted"] is False
    assert raw_data["job"]["title"] == "Old page title"
