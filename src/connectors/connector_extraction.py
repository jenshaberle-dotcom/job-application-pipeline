"""Bounded, dependency-free recipe interpreter. Transport and scheduling stay external."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

RUNTIME_VERSION = "jap.connector_extraction.v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_PAGES = 20
MAX_RECORDS = 2000


@dataclass(frozen=True, slots=True)
class ExtractionPlan:
    recipe_id: str
    origin_url: str
    request_url: str
    # Exact origins supplied by verified source/delegation evidence, never inferred.
    authorized_origins: tuple[str, ...]
    extractor: str
    records_path: tuple[str, ...] = ()
    id_path: tuple[str, ...] = ("id",)
    title_path: tuple[str, ...] = ("title",)
    url_path: tuple[str, ...] = ("url",)
    description_path: tuple[str, ...] = ("description",)
    locations_path: tuple[str, ...] = ("locations",)
    pagination: str = "single"
    offset_param: str = "skip"
    limit_param: str = "limit"
    page_size: int = 100
    max_pages: int = 5
    max_records: int = 1000
    # HTML selectors are deliberately limited to tag and optional attribute=value.
    html_fields: tuple[tuple[str, str, str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class AcquisitionResponse:
    url: str
    status: int
    body: str


@dataclass(frozen=True, slots=True)
class ExtractedJob:
    source_job_id: str
    title: str
    source_url: str
    description: str
    locations: tuple[str, ...]


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _origin(url: str) -> str:
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.fragment:
        raise ValueError("https_origin_without_credentials_required")
    if p.port not in (None, 443):
        raise ValueError("nonstandard_port_not_admitted")
    return f"https://{p.hostname.lower()}"


def _admitted(url: str, plan: ExtractionPlan) -> None:
    if _origin(url) not in plan.authorized_origins:
        raise ValueError("origin_not_authorized")


def validate_plan(plan: ExtractionPlan) -> None:
    if len(plan.recipe_id) != 64 or any(c not in "0123456789abcdef" for c in plan.recipe_id):
        raise ValueError("recipe_identity_required")
    if not plan.authorized_origins or any(
        _origin(value) != value for value in plan.authorized_origins
    ):
        raise ValueError("exact_authorized_origins_required")
    _admitted(plan.origin_url, plan)
    _admitted(plan.request_url, plan)
    if plan.extractor not in {"json", "jsonld", "html"}:
        raise ValueError("extractor_not_supported")
    if plan.pagination not in {"single", "offset"}:
        raise ValueError("explicit_pagination_required")
    if plan.extractor != "json" and plan.pagination != "single":
        raise ValueError("pagination_not_supported_for_extractor")
    if not 1 <= plan.max_pages <= MAX_PAGES or not 1 <= plan.max_records <= MAX_RECORDS:
        raise ValueError("execution_bounds_invalid")
    if not 1 <= plan.page_size <= MAX_RECORDS:
        raise ValueError("page_size_invalid")
    if plan.pagination == "offset" and (
        not plan.offset_param or not plan.limit_param or plan.offset_param == plan.limit_param
    ):
        raise ValueError("pagination_parameters_invalid")
    if plan.extractor == "html" and not plan.html_fields:
        raise ValueError("explicit_html_fields_required")


def _path(value: object, path: tuple[str, ...]) -> object:
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _text(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise TypeError("scalar_field_expected")
    return " ".join(unescape(str(value)).split())


def _locations(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        if isinstance(item, dict):
            address = item.get("address", item)
            if not isinstance(address, dict):
                raise TypeError("location_address_invalid")
            text = ", ".join(
                _text(address[k])
                for k in ("addressLocality", "addressRegion", "addressCountry")
                if address.get(k)
            )
        else:
            text = _text(item)
        if text:
            result.append(text)
    return tuple(sorted(set(result)))


class _HTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[dict] = []
        self.stack: list[dict] = []
        self.jsonld: list[str] = []
        self.script: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script" and (attributes.get("type") or "").lower() == "application/ld+json":
            self.script = []
        node = {"tag": tag, "attrs": attributes, "text": []}
        self.nodes.append(node)
        if tag not in {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.script is not None:
            self.jsonld.append("".join(self.script))
            self.script = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self.script is not None:
            self.script.append(data)
        if not any(node["tag"] in {"script", "style"} for node in self.stack):
            for node in self.stack:
                node["text"].append(data)


def _jsonld_jobs(value: object) -> list[dict]:
    if isinstance(value, list):
        return [item for child in value for item in _jsonld_jobs(child)]
    if not isinstance(value, dict):
        return []
    types = value.get("@type", [])
    types = types if isinstance(types, list) else [types]
    result = (
        [value] if any(str(t).rstrip("/").split("/")[-1] == "JobPosting" for t in types) else []
    )
    return result + _jsonld_jobs(value.get("@graph", []))


def _record(raw: dict, plan: ExtractionPlan, url: str) -> ExtractedJob:
    raw_url = _text(_path(raw, plan.url_path))
    if not raw_url:
        raise ValueError("exact_job_url_required")
    source_url = urljoin(url, raw_url)
    _admitted(source_url, plan)
    identity = _text(_path(raw, plan.id_path))
    title = _text(_path(raw, plan.title_path))
    description = _text(_path(raw, plan.description_path))
    if not identity or not title or not description:
        raise ValueError("job_identity_title_description_required")
    return ExtractedJob(
        identity, title, source_url, description, _locations(_path(raw, plan.locations_path))
    )


def extract_response(
    response: AcquisitionResponse, plan: ExtractionPlan
) -> tuple[ExtractedJob, ...]:
    _admitted(response.url, plan)
    if response.status != 200 or len(response.body.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError("response_status_or_size_invalid")
    if plan.extractor == "json":
        records = _path(json.loads(response.body), plan.records_path)
        if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
            raise ValueError("explicit_records_path_invalid")
        if len(records) > plan.max_records:
            raise ValueError("record_bound_exceeded")
        return tuple(_record(item, plan, response.url) for item in records)
    html = _HTML()
    html.feed(response.body)
    if plan.extractor == "jsonld":
        records = [item for raw in html.jsonld for item in _jsonld_jobs(json.loads(raw))]
        if len(records) > plan.max_records:
            raise ValueError("record_bound_exceeded")
        jobs = []
        for raw in records:
            identity = raw.get("identifier")
            if isinstance(identity, dict):
                identity = identity.get("value")
            source_url = urljoin(response.url, _text(raw.get("url")))
            _admitted(source_url, plan)
            title, description = _text(raw.get("title")), _text(raw.get("description"))
            if not title or not description:
                raise ValueError("job_identity_title_description_required")
            jobs.append(
                ExtractedJob(
                    _text(identity) or source_url,
                    title,
                    source_url,
                    description,
                    _locations(raw.get("jobLocation")),
                )
            )
        return tuple(jobs)
    raw = {}
    for field, tag, attribute, expected, value_attribute in plan.html_fields:
        matches = [
            node
            for node in html.nodes
            if node["tag"] == tag and (not attribute or node["attrs"].get(attribute) == expected)
        ]
        if len(matches) != 1:
            raise ValueError("html_selector_missing_or_ambiguous")
        raw[field] = (
            matches[0]["attrs"].get(value_attribute)
            if value_attribute
            else " ".join(matches[0]["text"])
        )
    return (_record(raw, plan, response.url),)


def execute_plan(
    plan: ExtractionPlan, fetch: Callable[[str], AcquisitionResponse]
) -> tuple[ExtractedJob, ...]:
    validate_plan(plan)
    jobs: dict[str, ExtractedJob] = {}
    page_digests = set()
    for index in range(plan.max_pages):
        url = plan.request_url
        if plan.pagination == "offset":
            p = urlsplit(url)
            params = [
                (k, v)
                for k, v in parse_qsl(p.query)
                if k not in {plan.offset_param, plan.limit_param}
            ]
            params.extend(
                [
                    (plan.offset_param, str(index * plan.page_size)),
                    (plan.limit_param, str(plan.page_size)),
                ]
            )
            url = urlunsplit((p.scheme, p.netloc, p.path, urlencode(params), ""))
        response = fetch(url)
        if response.url != url:
            raise ValueError("redirect_or_response_identity_mismatch")
        page = extract_response(response, plan)
        page_digest = digest([asdict(item) for item in page])
        if page and page_digest in page_digests:
            raise ValueError("pagination_not_advancing")
        page_digests.add(page_digest)
        for job in page:
            if job.source_job_id in jobs and jobs[job.source_job_id] != job:
                raise ValueError("conflicting_job_identity")
            jobs[job.source_job_id] = job
        if len(jobs) > plan.max_records:
            raise ValueError("record_bound_exceeded")
        if plan.pagination == "single" or len(page) < plan.page_size:
            return tuple(jobs[key] for key in sorted(jobs))
    raise ValueError("pagination_completion_not_proven")


def ats_plan(
    recipe_id: str, origin_url: str, api_url: str, authorized_origins: tuple[str, ...], family: str
) -> ExtractionPlan:
    """Source URLs are evidence inputs. Never guess company slugs or delegated hosts."""
    common = {
        "recipe_id": recipe_id,
        "origin_url": origin_url,
        "request_url": api_url,
        "authorized_origins": authorized_origins,
        "extractor": "json",
    }
    if family == "greenhouse":
        plan = ExtractionPlan(
            **common,
            records_path=("jobs",),
            url_path=("absolute_url",),
            description_path=("content",),
            locations_path=("location", "name"),
        )
    elif family == "lever":
        plan = ExtractionPlan(
            **common,
            title_path=("text",),
            url_path=("hostedUrl",),
            description_path=("descriptionPlain",),
            locations_path=("categories", "location"),
            pagination="offset",
        )
    else:
        raise ValueError("ats_family_not_implemented")
    validate_plan(plan)
    return plan


def fingerprint_saved_responses(
    plan: ExtractionPlan, responses: tuple[AcquisitionResponse, ...]
) -> tuple[str, ...]:
    """Propose capabilities from bounded admitted captures; never from employer names."""
    validate_plan(plan)
    jobs = [job for response in responses for job in extract_response(response, plan)]
    if not jobs:
        return ()
    if plan.extractor == "jsonld":
        return ("structured_jobposting_inventory", "structured_jobposting_detail")
    if plan.extractor != "json":
        return ()
    tags = {"explicit_json_job_inventory", "full_job_content"}
    parsed = urlsplit(plan.request_url)
    if (
        parsed.hostname == "boards-api.greenhouse.io"
        and parsed.path.startswith("/v1/boards/")
        and parsed.path.endswith("/jobs")
        and plan.records_path == ("jobs",)
        and plan.url_path == ("absolute_url",)
        and plan.description_path == ("content",)
    ):
        tags.update({"provider:greenhouse", "authorized_provider_host"})
    elif (
        parsed.hostname in {"api.lever.co", "api.eu.lever.co"}
        and parsed.path.startswith("/v0/postings/")
        and plan.records_path == ()
        and plan.title_path == ("text",)
        and plan.url_path == ("hostedUrl",)
        and plan.description_path == ("descriptionPlain",)
    ):
        tags.update({"provider:lever", "authorized_provider_host"})
    return tuple(sorted(tags))


def qualify_extraction(
    plan: ExtractionPlan,
    responses: tuple[AcquisitionResponse, ...],
    expected_jobs: tuple[ExtractedJob, ...],
) -> dict[str, object]:
    """Offline golden-response replay. Does not claim current live-source health."""
    if not expected_jobs:
        raise ValueError("nonempty_expected_jobs_required")
    by_url = {item.url: item for item in responses}
    if len(by_url) != len(responses):
        raise ValueError("duplicate_response_identity")
    consumed = set()

    def replay(url: str) -> AcquisitionResponse:
        if url not in by_url:
            raise ValueError("response_evidence_missing")
        consumed.add(url)
        return by_url[url]

    actual = execute_plan(plan, replay)
    expected = tuple(sorted(expected_jobs, key=lambda item: item.source_job_id))
    if len({item.source_job_id for item in expected}) != len(expected):
        raise ValueError("expected_identity_duplicate")
    if actual != expected or consumed != set(by_url):
        raise ValueError("extraction_contract_mismatch")
    payload = {
        "schema_version": "jap.connector_extraction_proof.v1",
        "runtime_version": RUNTIME_VERSION,
        "recipe_id": plan.recipe_id,
        "plan_digest": digest(asdict(plan)),
        "responses_digest": digest(
            [asdict(item) for item in sorted(responses, key=lambda item: item.url)]
        ),
        "expected_digest": digest([asdict(item) for item in expected]),
        "job_count": len(actual),
        "status": "PASS",
        "scope": "OFFLINE_RESPONSE_REPLAY",
        "runtime_admitted": False,
    }
    return {**payload, "proof_id": digest(payload)}
