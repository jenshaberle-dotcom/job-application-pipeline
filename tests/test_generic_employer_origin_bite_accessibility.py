from src.connectors.employer_origin_bite import BitePosting
from src.connectors.generic_employer_origin_product_bite import (
    project_bite_accessibility_evidence,
)
from src.connectors.generic_job_detail_evidence import (
    EVIDENCE_SCHEMA,
    project_detail_evidence_into_raw_data,
)
from src.silver.relevance import get_accessibility_matches


def _posting(*, remote: object = "ja") -> BitePosting:
    return BitePosting(
        posting_id="abc123",
        title="Senior Data Engineer",
        url="https://jobs.example.test/jobposting/abc123",
        apply_url="https://jobs.example.test/jobposting/abc123/apply",
        employer_name="Example GmbH",
        raw={
            "address": {"city": "Hannover"},
            "custom": {"ort": "bundesweit", "remote": remote},
        },
    )


def _evidence() -> dict:
    return {
        "schema": EVIDENCE_SCHEMA,
        "methods": ["plain_text"],
        "parser_family": "plain_text",
        "field_presence": {"locations": False, "remote": False},
        "locations": [],
        "structured_locations": [],
        "applicant_locations": [],
        "remote": None,
    }


def test_bite_inventory_projects_explicit_location_and_remote_into_generic_evidence() -> None:
    evidence = project_bite_accessibility_evidence(_evidence(), _posting())

    assert evidence["locations"] == ["Hannover", "bundesweit"]
    assert evidence["remote"] is True
    assert evidence["field_presence"]["locations"] is True
    assert evidence["field_presence"]["remote"] is True
    assert "bite_inventory_structured_accessibility" in evidence["methods"]

    raw_data = project_detail_evidence_into_raw_data(
        {
            "source_type": "employer_origin_career_site",
            "source_family": "generic_origin",
            "job": {
                "title": "Senior Data Engineer",
                "company_name": "Example GmbH",
            },
        },
        evidence,
    )

    assert raw_data["job"]["location"] == "Hannover | bundesweit"
    assert raw_data["job"]["metadata"]["workplace_type"] == "remote"

    raw_job = {
        "source_name": "generic_origin:example",
        "source_url": "https://jobs.example.test/jobposting/abc123",
        "raw_data": raw_data,
    }
    matches = get_accessibility_matches(raw_job)
    assert "hannover" in matches
    assert "remote" in matches


def test_bite_remote_projection_is_fail_closed_for_unknown_values() -> None:
    evidence = project_bite_accessibility_evidence(
        _evidence(),
        _posting(remote="gelegentlich"),
    )

    assert evidence["remote"] is None
    assert evidence["field_presence"]["remote"] is False
    assert evidence["locations"] == ["Hannover", "bundesweit"]
