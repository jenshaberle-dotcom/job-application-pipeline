from __future__ import annotations

import json

from src.connectors.employer_origin_greenhouse_navigation import (
    explicit_greenhouse_board_token,
    greenhouse_detail_urls_from_jobs,
    greenhouse_metadata_matches_employer,
)


def test_greenhouse_token_requires_one_concrete_canonical_board_reference() -> None:
    html = (
        '<script src="https://boards-api.greenhouse.io/v1/boards/commercetools/jobs?content=true"></script>'
    )
    assert explicit_greenhouse_board_token(html) == "commercetools"
    assert explicit_greenhouse_board_token("greenhouse careers") is None
    assert explicit_greenhouse_board_token(
        html + '<a href="https://job-boards.greenhouse.io/other/jobs/123456">Other</a>'
    ) is None


def test_greenhouse_token_accepts_static_binding_only_with_exact_jobs_api_template() -> None:
    html = """
    <script>
      const BOARD = 'commercetools';
      const res = await fetch(
        'https://boards-api.greenhouse.io/v1/boards/' + BOARD + '/jobs?content=true'
      );
    </script>
    """
    assert explicit_greenhouse_board_token(html) == "commercetools"

    assert explicit_greenhouse_board_token(
        "<script>const BOARD = 'commercetools';</script>"
    ) is None
    assert explicit_greenhouse_board_token(
        """
        <script>
          const BOARD = 'commercetools';
          fetch('https://example.invalid/v1/boards/' + BOARD + '/jobs');
        </script>
        """
    ) is None


def test_greenhouse_static_binding_fails_closed_on_conflicting_evidence() -> None:
    html = """
    <script>
      const BOARD = 'commercetools';
      fetch('https://boards-api.greenhouse.io/v1/boards/' + BOARD + '/jobs?content=true');
    </script>
    <a href="https://job-boards.greenhouse.io/other/jobs/123456">Other</a>
    """
    assert explicit_greenhouse_board_token(html) is None


def test_greenhouse_static_binding_supports_exact_template_literal_reference() -> None:
    html = """
    <script>
      const boardToken = "commercetools";
      fetch(`https://boards-api.greenhouse.io/v1/boards/${boardToken}/jobs?content=true`);
    </script>
    """
    assert explicit_greenhouse_board_token(html) == "commercetools"


def test_greenhouse_metadata_identity_is_bound_to_employer_host() -> None:
    assert greenhouse_metadata_matches_employer(
        body=json.dumps({"name": "commercetools"}),
        employer_url="https://commercetools.com/careers",
    )
    assert not greenhouse_metadata_matches_employer(
        body=json.dumps({"name": "unrelated employer"}),
        employer_url="https://commercetools.com/careers",
    )


def test_greenhouse_jobs_emit_only_token_consistent_concrete_details() -> None:
    body = json.dumps(
        {
            "jobs": [
                {
                    "id": 7774985003,
                    "absolute_url": "https://job-boards.greenhouse.io/commercetools/jobs/7774985003",
                },
                {
                    "id": 7774985004,
                    "absolute_url": "https://job-boards.greenhouse.io/other/jobs/7774985004",
                },
                {
                    "id": 1,
                    "absolute_url": "https://example.invalid/commercetools/jobs/7774985005",
                },
            ]
        }
    )
    assert greenhouse_detail_urls_from_jobs(body=body, board_token="commercetools") == (
        "https://job-boards.greenhouse.io/commercetools/jobs/7774985003",
    )
