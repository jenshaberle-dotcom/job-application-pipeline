from __future__ import annotations

import socket

from src.search_intelligence.detail_semantics_deterministic import extract_job_postings
from src.search_intelligence.product_v1_downstream_preview import (
    fetch_public_https_detail_document,
    fetch_public_https_detail_text,
)


class _Response:
    def __init__(self, body: str) -> None:
        self.status_code = 200
        self.headers = {"Content-Type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"
        self._body = body.encode("utf-8")
        self.closed = False

    def iter_content(self, *, chunk_size: int):
        assert chunk_size > 0
        yield self._body

    def close(self) -> None:
        self.closed = True


class _Session:
    def __init__(self, body: str) -> None:
        self.body = body
        self.responses: list[_Response] = []

    def get(self, url: str, **kwargs):
        assert url == "https://jobs.example.com/42"
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        response = _Response(self.body)
        self.responses.append(response)
        return response


def _resolver(_host: str, port: int, *, type: int):
    assert type == socket.SOCK_STREAM
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]


def _html() -> str:
    return """
    <html>
      <head>
        <title>Senior Data Engineer</title>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Senior Data Engineer",
            "skills": "Python, SQL",
            "jobLocationType": "TELECOMMUTE"
          }
        </script>
      </head>
      <body>Build data pipelines with Python and SQL. Remote work is available.</body>
    </html>
    """


def test_detail_document_keeps_jsonld_in_memory_while_visible_text_stays_clean() -> None:
    session = _Session(_html())

    document = fetch_public_https_detail_document(
        "https://jobs.example.com/42",
        session=session,
        resolver=_resolver,
    )

    assert document.final_url == "https://jobs.example.com/42"
    assert document.title == "Senior Data Engineer"
    assert "Build data pipelines with Python and SQL" in document.text
    assert '"@type": "JobPosting"' not in document.text
    assert '"@type": "JobPosting"' in document.html
    postings = extract_job_postings(document.html)
    assert len(postings) == 1
    assert postings[0]["title"] == "Senior Data Engineer"
    assert postings[0]["skills"] == "Python, SQL"
    assert session.responses[0].closed is True


def test_existing_text_fetch_contract_remains_unchanged() -> None:
    session = _Session(_html())

    final_url, title, text = fetch_public_https_detail_text(
        "https://jobs.example.com/42",
        session=session,
        resolver=_resolver,
    )

    assert final_url == "https://jobs.example.com/42"
    assert title == "Senior Data Engineer"
    assert "Remote work is available" in text
    assert "application/ld+json" not in text
    assert session.responses[0].closed is True
