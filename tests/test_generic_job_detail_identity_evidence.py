from src.connectors.generic_job_detail_evidence import (
    extract_generic_job_detail_evidence,
    project_detail_evidence_into_raw_data,
)


def test_explicit_label_identifier_is_extracted_without_employer_special_case() -> None:
    html = """
    <html><head><title>Data Platform Engineer</title></head>
    <body>
      <main>
        <h1>Data Platform Engineer (m/w/d)</h1>
        <p>Python, Kubernetes and data-platform engineering.</p>
        <p>Wir freuen uns auf Ihre Bewerbung unter Angabe der Kennziffer 392/B.</p>
      </main>
    </body></html>
    """

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://www.example.de/de/karriere/offene-stellen/data-platform-engineer",
        page_title="Data Platform Engineer",
    )

    assert evidence["identifier"] == "392/B"
    assert evidence["identifier_evidence_kind"] == "explicit_label"
    assert evidence["identifier_label"] == "kennziffer"
    assert evidence["vacancy_identity_kind"] == "explicit_label_identifier"
    assert evidence["field_presence"]["identifier"] is True
    assert "explicit_label:vacancy_identifier" in evidence["methods"]
    assert evidence["raw_html_persisted"] is False


def test_schema_identifier_keeps_priority_over_visible_label() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Data Engineer",
        "description": "Build data products",
        "identifier": "REQ-900"
      }
      </script>
    </head><body>
      <p>Job ID: PAGE-777</p>
    </body></html>
    """

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://jobs.example.de/job/data-engineer",
    )

    assert evidence["identifier"] == "REQ-900"
    assert evidence["identifier_evidence_kind"] == "schema_org"
    assert evidence["identifier_label"] is None
    assert evidence["vacancy_identity_kind"] == "structured_identifier"


def test_canonical_origin_url_is_preserved_as_identity_evidence() -> None:
    html = """
    <html><head>
      <link rel="canonical" href="/karriere/offene-stellen/data-engineer">
      <title>Data Engineer</title>
    </head><body><p>Python SQL data platform</p></body></html>
    """

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://www.example.de/de/karriere/offene-stellen/data-engineer",
    )

    assert evidence["canonical_origin_url"] == (
        "https://www.example.de/karriere/offene-stellen/data-engineer"
    )
    assert evidence["vacancy_identity_kind"] == "canonical_origin_url"
    assert evidence["field_presence"]["canonical_origin_url"] is True

    projected = project_detail_evidence_into_raw_data(
        {
            "job": {
                "title": "Data Engineer",
                "source_url": "https://www.example.de/de/karriere/offene-stellen/data-engineer",
            }
        },
        evidence,
    )
    metadata = projected["job"]["metadata"]
    assert metadata["canonical_origin_url"] == (
        "https://www.example.de/karriere/offene-stellen/data-engineer"
    )
    assert metadata["vacancy_identity_kind"] == "canonical_origin_url"


def test_unlabelled_numbers_do_not_become_job_identity() -> None:
    html = """
    <html><head><title>Platform Engineer</title></head>
    <body><p>Over 5000 colleagues in 3 locations. Founded in 1992.</p></body></html>
    """

    evidence = extract_generic_job_detail_evidence(
        html=html,
        url="https://example.de/jobs/platform-engineer",
    )

    assert evidence["identifier"] is None
    assert evidence["identifier_evidence_kind"] is None
    assert evidence["vacancy_identity_kind"] == "source_url"
