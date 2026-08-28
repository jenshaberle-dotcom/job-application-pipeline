"""Strict Workday CXS detail projection for unchanged genuine-job proof.

This module is intentionally read-only and side-effect free. It derives one exact
same-host CXS detail endpoint only from an already-authorized Workday board plus a
concrete public detail URL. The structured response must expose a bounded
``jobPostingInfo`` record with a real title, description, and identity before it
can be projected into ``PageSnapshot`` evidence.

The projection deliberately excludes the surrounding JSON keys. In particular,
``jobPostingInfo`` itself must never satisfy the canonical ``jobposting`` content
marker by accident. Final acceptance remains exclusively with the unchanged
``genuine_job_detail_proof`` caller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlparse

from src.connectors.employer_origin_acquisition import (
    PageSnapshot,
    canonical_url,
    parse_page,
    url_host,
)
from src.connectors.employer_origin_workday_navigation import workday_board_route


MAX_TITLE_CHARS = 500
MAX_IDENTITY_CHARS = 500
MAX_DESCRIPTION_CHARS = 5_000_000


@dataclass(frozen=True)
class WorkdayCxsDetail:
    title: str
    description_html: str
    job_req_id: str
    job_posting_id: str

    @property
    def identity(self) -> str:
        return self.job_req_id or self.job_posting_id


def _scalar(value: object, *, limit: int) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if not isinstance(value, (str, int, float)):
        return ""
    text = " ".join(str(value).split()).strip()
    if not text or len(text) > limit:
        return ""
    return text


def workday_cxs_detail_url(
    public_detail_url: str,
    *,
    public_board_url: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> str | None:
    """Derive the exact CXS detail endpoint without guessing tenant/site/identity."""

    board = workday_board_route(public_board_url, allowed_hosts=allowed_hosts)
    if board is None:
        return None

    clean = canonical_url(public_detail_url)
    parsed = urlparse(clean)
    if (
        parsed.scheme.casefold() != "https"
        or url_host(clean) != board.host
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        return None

    board_path = urlparse(board.public_board_url).path.rstrip("/")
    prefix = f"{board_path}/job/"
    if not parsed.path.startswith(prefix):
        return None

    relative = parsed.path[len(board_path) :]
    if (
        len(relative) > 1_500
        or not relative.startswith("/job/")
        or "//" in relative
        or any(segment in {".", ".."} for segment in relative.split("/"))
    ):
        return None

    return f"https://{board.host}/wday/cxs/{board.tenant}/{board.site}{relative}"


def parse_workday_cxs_detail(body: str) -> WorkdayCxsDetail | None:
    """Parse only a strong bounded ``jobPostingInfo`` detail record."""

    if not isinstance(body, str) or len(body) > MAX_DESCRIPTION_CHARS + 1_000_000:
        return None
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None

    info = payload.get("jobPostingInfo")
    if not isinstance(info, dict):
        return None

    title = _scalar(info.get("title"), limit=MAX_TITLE_CHARS)
    description = info.get("jobDescription")
    description_html = description.strip() if isinstance(description, str) else ""
    job_req_id = _scalar(info.get("jobReqId"), limit=MAX_IDENTITY_CHARS)
    job_posting_id = _scalar(info.get("jobPostingId"), limit=MAX_IDENTITY_CHARS)

    if (
        not title
        or not description_html
        or len(description_html) < 120
        or len(description_html) > MAX_DESCRIPTION_CHARS
        or not (job_req_id or job_posting_id)
    ):
        return None

    return WorkdayCxsDetail(
        title=title,
        description_html=description_html,
        job_req_id=job_req_id,
        job_posting_id=job_posting_id,
    )


def workday_cxs_detail_page(
    *,
    public_detail_url: str,
    public_board_url: str,
    response_url: str,
    status_code: int,
    body: str,
    allowed_hosts: tuple[str, ...] | set[str],
) -> PageSnapshot | None:
    """Project exact CXS detail evidence into a canonical proof input.

    The returned snapshot describes the actual CXS response URL, not the public
    SPA URL. Only the provider-supplied title and description are projected. The
    caller must still invoke ``genuine_job_detail_proof(..., known_detail=True)``.
    """

    expected = workday_cxs_detail_url(
        public_detail_url,
        public_board_url=public_board_url,
        allowed_hosts=allowed_hosts,
    )
    if (
        expected is None
        or int(status_code) >= 400
        or canonical_url(response_url) != expected
        or url_host(response_url) != url_host(expected)
    ):
        return None

    detail = parse_workday_cxs_detail(body)
    if detail is None:
        return None

    parsed_description = parse_page(
        requested_url=expected,
        html=detail.description_html,
        final_url=expected,
        status_code=int(status_code),
    )
    return PageSnapshot(
        requested_url=expected,
        final_url=expected,
        status_code=int(status_code),
        title=detail.title,
        text=parsed_description.text,
        html=detail.description_html,
        links=parsed_description.links,
    )


__all__ = [
    "WorkdayCxsDetail",
    "parse_workday_cxs_detail",
    "workday_cxs_detail_page",
    "workday_cxs_detail_url",
]
