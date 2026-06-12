from __future__ import annotations

import csv
import json
import os
import urllib.error
import urllib.request
import unicodedata
from urllib.parse import urlparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCHEMA_VERSION = "expand002.controlled_external_probe_trial_run.v1"
WORK_ITEM = "EXPAND-002 Controlled External Probe Trial Run"
INPUT_SCHEMA_PREFIX = "market003f.expand001_controlled_manual_candidate_pipeline_trial"
NO_MUTATION_BOUNDARY = (
    "external_probe_trial_only_no_automatic_candidate_creation_no_gate_decision_no_connector_activation"
)
DEFAULT_STAGES = ("origin_url_discovery_probe", "detail_page_evidence_probe")
DISALLOWED_ACTIONS = (
    "create_candidate_automatically",
    "promote_candidate_automatically",
    "write_gate_decision",
    "activate_connector",
    "mutate_bronze_silver_gold",
    "change_scheduler",
    "write_database_state",
)
ALLOWED_ARTIFACT_ACTIONS = (
    "execute_explicit_external_probe_trial",
    "write_probe_result_exports",
    "summarize_stop_reasons_for_human_review",
)

STRONG_EVIDENCE_HINTS = frozenset(
    {
        "company_specific_job_detail_hint_found",
        "origin_or_career_hint_found",
    }
)
WEAK_EVIDENCE_HINTS = frozenset(
    {
        "weak_market_or_aggregator_hint_found",
        "generic_web_hint_found",
    }
)
PROVIDER_AUTH_FAILURE_HINTS = frozenset(
    {
        "provider_auth_failed_requires_key_review",
        "blocked_after_provider_auth_failure",
    }
)
URL_EVIDENCE_CLASSES = frozenset(
    {
        "company_origin_or_career_url",
        "company_specific_job_detail_url",
        "origin_provider_url",
        "aggregator_or_market_url",
        "unrelated_or_generic_url",
    }
)
STRONG_URL_EVIDENCE_CLASSES = frozenset(
    {
        "company_origin_or_career_url",
        "company_specific_job_detail_url",
        "origin_provider_url",
    }
)
WEAK_MARKET_OR_AGGREGATOR_HOSTS = frozenset(
    {
        "arbeitnow.com",
        "bebee.com",
        "broxer.com",
        "dailyremote.com",
        "datacareer.de",
        "devjobs.de",
        "germantechjobs.de",
        "glassdoor.com",
        "himalayas.app",
        "indeed.com",
        "indeed.de",
        "jobgether.com",
        "jobleads.com",
        "jobswithscala.com",
        "kununu.com",
        "linkedin.com",
        "meetfrank.com",
        "nextleveljobs.eu",
        "qualitycontracts.co.uk",
        "remotely.de",
        "remoterocketship.com",
        "stepstone.de",
        "wearedevelopers.com",
        "wellfound.com",
        "xing.com",
    }
)
ORIGIN_PROVIDER_HOSTS = frozenset(
    {
        "ashbyhq.com",
        "dvinci.de",
        "greenhouse.io",
        "join.com",
        "lever.co",
        "onlyfy.jobs",
        "personio.de",
        "recruitee.com",
        "smartrecruiters.com",
        "softgarden.io",
        "successfactors.com",
        "taleo.net",
        "teamtailor.com",
        "workable.com",
        "workdayjobs.com",
        "zohorecruit.com",
    }
)
GENERIC_COMPANY_TOKEN_STOPWORDS = frozenset(
    {
        "ag",
        "analytics",
        "business",
        "cloud",
        "company",
        "consulting",
        "data",
        "de",
        "digital",
        "engineer",
        "engineering",
        "fire",
        "fuer",
        "fur",
        "gesellschaft",
        "gmbh",
        "group",
        "gruppe",
        "holding",
        "informatik",
        "it",
        "jobs",
        "kg",
        "mbh",
        "service",
        "services",
        "software",
        "solutions",
        "systems",
        "technologies",
        "technology",
        "the",
    }
)
CAREER_PATH_TOKENS = frozenset(
    {
        "career",
        "careers",
        "jobs",
        "job",
        "karriere",
        "stellen",
        "stellenangebote",
        "einstiegsmoeglichkeiten",
        "openings",
        "roles",
        "vacancies",
        "vacancy",
        "work-with-us",
        "workwithus",
    }
)
ROLE_HINT_TOKENS = frozenset(
    {
        "data engineer",
        "analytics engineer",
        "cloud data engineer",
        "data analyst",
        "business intelligence",
        "bi engineer",
        "etl",
        "data analytics",
    }
)

Transport = Callable[[str, Mapping[str, Any], str | None], Mapping[str, Any]]


@dataclass(frozen=True)
class ProbeQuery:
    probe_id: str
    trial_id: str
    company_key: str
    company_name: str
    stage: str
    query: str
    max_results: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProbeResult:
    probe_id: str
    trial_id: str
    company_key: str
    company_name: str
    stage: str
    query: str
    provider: str
    status: str
    request_executed: bool
    result_count: int
    urls: tuple[str, ...]
    titles: tuple[str, ...]
    evidence_hint: str
    url_evidence_classes: tuple[str, ...] = ()
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["urls"] = list(self.urls)
        data["titles"] = list(self.titles)
        data["url_evidence_classes"] = list(self.url_evidence_classes)
        return data


def safety_boundary(*, execute_external_probes: bool) -> dict[str, bool]:
    return {
        "read_only_artifact_run": True,
        "external_requests_allowed_by_explicit_operator_flag": True,
        "external_requests_executed_by_this_command": bool(execute_external_probes),
        "database_writes": False,
        "pipeline_mutation": False,
        "candidate_creation": False,
        "candidate_promotion": False,
        "candidate_or_gate_mutation": False,
        "gate_decision": False,
        "connector_activation": False,
        "scheduler_mutation": False,
        "bronze_silver_gold_mutation": False,
    }


def build_probe_queries(
    trial_candidate: Mapping[str, Any],
    *,
    max_queries_per_candidate: int = 2,
    max_results_per_query: int = 5,
) -> list[ProbeQuery]:
    company_key = _text(trial_candidate.get("company_key"), default="unknown_company")
    company_name = _text(trial_candidate.get("company_name"), default=company_key)
    trial_id = _text(trial_candidate.get("trial_id"), default=f"expand001::{company_key}")
    templates = [
        (
            "origin_url_discovery_probe",
            f'{company_name} careers jobs Data Engineer Analytics Engineer Germany remote Hannover',
        ),
        (
            "detail_page_evidence_probe",
            f'{company_name} job Data Engineer Analytics Engineer remote Germany career site',
        ),
    ]
    queries: list[ProbeQuery] = []
    for index, (stage, query) in enumerate(templates[: max(0, max_queries_per_candidate)], start=1):
        queries.append(
            ProbeQuery(
                probe_id=f"expand002::{company_key}::{stage}::{index}",
                trial_id=trial_id,
                company_key=company_key,
                company_name=company_name,
                stage=stage,
                query=_clip_query(query),
                max_results=max_results_per_query,
            )
        )
    return queries


def select_trial_candidates(
    plan: Mapping[str, Any],
    *,
    max_candidates: int | None = 200,
    eligible_only: bool = True,
) -> list[dict[str, Any]]:
    raw_candidates = _ensure_mapping_list(plan.get("trial_candidates"))
    selected: list[dict[str, Any]] = []
    for candidate in raw_candidates:
        if eligible_only and not bool(candidate.get("eligible_for_explicit_external_probe")):
            continue
        selected.append(dict(candidate))
    selected.sort(
        key=lambda item: (
            _int(item.get("trial_priority_rank"), default=999),
            _text(item.get("company_name"), default="").lower(),
            _text(item.get("company_key"), default=""),
        )
    )
    if max_candidates is not None:
        selected = selected[: max(0, max_candidates)]
    return selected


def build_probe_manifest(
    plan: Mapping[str, Any],
    *,
    max_candidates: int | None = 200,
    max_queries_per_candidate: int = 2,
    max_results_per_query: int = 5,
    max_total_requests: int = 500,
) -> list[ProbeQuery]:
    manifest, _diagnostics = build_probe_manifest_with_diagnostics(
        plan,
        max_candidates=max_candidates,
        max_queries_per_candidate=max_queries_per_candidate,
        max_results_per_query=max_results_per_query,
        max_total_requests=max_total_requests,
    )
    return manifest


def build_probe_manifest_with_diagnostics(
    plan: Mapping[str, Any],
    *,
    max_candidates: int | None = 200,
    max_queries_per_candidate: int = 2,
    max_results_per_query: int = 5,
    max_total_requests: int = 500,
) -> tuple[list[ProbeQuery], dict[str, int]]:
    raw_candidates = _ensure_mapping_list(plan.get("trial_candidates"))
    eligible_candidates = [dict(candidate) for candidate in raw_candidates if bool(candidate.get("eligible_for_explicit_external_probe"))]
    eligible_candidates.sort(
        key=lambda item: (
            _int(item.get("trial_priority_rank"), default=999),
            _text(item.get("company_name"), default="").lower(),
            _text(item.get("company_key"), default=""),
            _text(item.get("trial_id"), default=""),
        )
    )

    selected_candidates: list[dict[str, Any]] = []
    seen_candidates: set[tuple[str, str]] = set()
    duplicate_candidate_count = 0
    for candidate in eligible_candidates:
        identity = _candidate_identity(candidate)
        if identity in seen_candidates:
            duplicate_candidate_count += 1
            continue
        seen_candidates.add(identity)
        selected_candidates.append(candidate)

    if max_candidates is not None:
        selected_candidates = selected_candidates[: max(0, max_candidates)]

    raw_queries: list[ProbeQuery] = []
    for candidate in selected_candidates:
        raw_queries.extend(
            build_probe_queries(
                candidate,
                max_queries_per_candidate=max_queries_per_candidate,
                max_results_per_query=max_results_per_query,
            )
        )

    manifest: list[ProbeQuery] = []
    seen_probes: set[tuple[str, str, str, str]] = set()
    duplicate_probe_count = 0
    for query in raw_queries:
        key = (query.probe_id, query.trial_id, query.stage, query.query)
        if key in seen_probes:
            duplicate_probe_count += 1
            continue
        seen_probes.add(key)
        manifest.append(query)

    manifest = manifest[: max(0, max_total_requests)]
    diagnostics = {
        "raw_candidate_count": len(raw_candidates),
        "eligible_candidate_count": len(eligible_candidates),
        "selected_candidate_count": len(selected_candidates),
        "duplicate_candidate_count": duplicate_candidate_count,
        "raw_probe_count_before_probe_dedupe": len(raw_queries),
        "duplicate_probe_count": duplicate_probe_count,
        "planned_probe_count_after_dedupe_and_cap": len(manifest),
    }
    return manifest, diagnostics

def build_trial_run_report(
    plan: Mapping[str, Any],
    *,
    execute_external_probes: bool = False,
    provider: str = "dry_run",
    max_candidates: int | None = 200,
    max_queries_per_candidate: int = 2,
    max_results_per_query: int = 5,
    max_total_requests: int = 500,
    generated_at: str | None = None,
    input_path: str | None = None,
    transport: Transport | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    manifest, manifest_diagnostics = build_probe_manifest_with_diagnostics(
        plan,
        max_candidates=max_candidates,
        max_queries_per_candidate=max_queries_per_candidate,
        max_results_per_query=max_results_per_query,
        max_total_requests=max_total_requests,
    )
    results = run_probe_manifest(
        manifest,
        execute_external_probes=execute_external_probes,
        provider=provider,
        transport=transport,
        api_key=api_key,
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "input_path": input_path,
        "input_schema_version": plan.get("schema_version"),
        "safety_boundary": safety_boundary(execute_external_probes=execute_external_probes),
        "interpretation_boundary": (
            "This report records a controlled external probe trial for manually discovered candidates. "
            "It may execute external search requests only when explicitly requested by the operator. "
            "It never creates candidates, writes gate decisions, activates connectors, mutates Bronze/Silver/Gold, "
            "writes database state, or changes scheduler behavior. Results are evidence/review artifacts only. "
            "Weak market/aggregator hints are learning signals only and are not origin/detail evidence."
        ),
        "run_policy": build_run_policy(
            execute_external_probes=execute_external_probes,
            provider=provider,
            max_candidates=max_candidates,
            max_queries_per_candidate=max_queries_per_candidate,
            max_results_per_query=max_results_per_query,
            max_total_requests=max_total_requests,
        ),
        "manifest_diagnostics": manifest_diagnostics,
        "mutation_counts": mutation_counts(external_requests=sum(1 for result in results if result.request_executed)),
        "summary": build_summary(manifest, results, manifest_diagnostics=manifest_diagnostics),
        "probe_manifest": [query.as_dict() for query in manifest],
        "probe_results": [result.as_dict() for result in results],
        "candidate_results": build_candidate_results(results),
    }
    return report

def build_missing_input_report(path: Path, *, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated_at or datetime.now(timezone.utc).isoformat(),
        "work_item": WORK_ITEM,
        "input_path": str(path),
        "input_status": "input_missing",
        "input_warning": "Run scripts/run_market003f_expand001_controlled_manual_candidate_pipeline_trial.py first.",
        "safety_boundary": safety_boundary(execute_external_probes=False),
        "run_policy": build_run_policy(execute_external_probes=False, provider="dry_run"),
        "mutation_counts": mutation_counts(external_requests=0),
        "summary": empty_summary(),
        "probe_manifest": [],
        "probe_results": [],
        "candidate_results": [],
    }


def build_invalid_input_report(path: Path, error: str, *, generated_at: str | None = None) -> dict[str, Any]:
    report = build_missing_input_report(path, generated_at=generated_at)
    report["input_status"] = "input_invalid"
    report["input_warning"] = error
    return report


def run_probe_manifest(
    manifest: Sequence[ProbeQuery],
    *,
    execute_external_probes: bool,
    provider: str,
    transport: Transport | None = None,
    api_key: str | None = None,
) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    normalized_provider = provider.strip().lower() or "dry_run"
    provider_auth_failed = False
    for query in manifest:
        if not execute_external_probes:
            results.append(
                ProbeResult(
                    probe_id=query.probe_id,
                    trial_id=query.trial_id,
                    company_key=query.company_key,
                    company_name=query.company_name,
                    stage=query.stage,
                    query=query.query,
                    provider="dry_run",
                    status="planned_not_executed",
                    request_executed=False,
                    result_count=0,
                    urls=(),
                    titles=(),
                    evidence_hint="not_executed",
                )
            )
            continue
        if provider_auth_failed:
            results.append(
                ProbeResult(
                    probe_id=query.probe_id,
                    trial_id=query.trial_id,
                    company_key=query.company_key,
                    company_name=query.company_name,
                    stage=query.stage,
                    query=query.query,
                    provider=normalized_provider,
                    status="blocked_after_provider_auth_failure",
                    request_executed=False,
                    result_count=0,
                    urls=(),
                    titles=(),
                    evidence_hint="blocked_after_provider_auth_failure",
                    error="Skipped after provider authentication failure to avoid repeated failed external requests.",
                )
            )
            continue
        try:
            payload = execute_probe(query, provider=normalized_provider, transport=transport, api_key=api_key)
        except Exception as exc:  # noqa: BLE001 - preserve trial result instead of crashing partial run.
            is_auth_error = _is_provider_auth_failure(exc)
            provider_auth_failed = provider_auth_failed or is_auth_error
            results.append(
                ProbeResult(
                    probe_id=query.probe_id,
                    trial_id=query.trial_id,
                    company_key=query.company_key,
                    company_name=query.company_name,
                    stage=query.stage,
                    query=query.query,
                    provider=normalized_provider,
                    status="request_failed",
                    request_executed=True,
                    result_count=0,
                    urls=(),
                    titles=(),
                    evidence_hint="provider_auth_failed_requires_key_review" if is_auth_error else "request_failed",
                    error=str(exc),
                )
            )
        else:
            extracted = extract_search_results(payload)
            urls = tuple(item["url"] for item in extracted)
            titles = tuple(item["title"] for item in extracted)
            url_evidence_classes = classify_url_evidence_classes(query, urls, titles)
            results.append(
                ProbeResult(
                    probe_id=query.probe_id,
                    trial_id=query.trial_id,
                    company_key=query.company_key,
                    company_name=query.company_name,
                    stage=query.stage,
                    query=query.query,
                    provider=normalized_provider,
                    status="completed",
                    request_executed=True,
                    result_count=len(extracted),
                    urls=urls,
                    titles=titles,
                    evidence_hint=classify_evidence_hint_from_url_classes(url_evidence_classes),
                    url_evidence_classes=url_evidence_classes,
                )
            )
    return results

def execute_probe(
    query: ProbeQuery,
    *,
    provider: str,
    transport: Transport | None = None,
    api_key: str | None = None,
) -> Mapping[str, Any]:
    if provider == "fake":
        return fake_search_payload(query)
    if provider == "tavily":
        key = api_key or os.getenv("TAVILY_API_KEY")
        if not key:
            raise ValueError("TAVILY_API_KEY is required for provider=tavily")
        payload = {
            "query": query.query,
            "search_depth": "basic",
            "max_results": query.max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        if transport is not None:
            return transport("https://api.tavily.com/search", payload, key)
        return tavily_post_json("https://api.tavily.com/search", payload, key)
    raise ValueError(f"Unsupported provider: {provider}")


def tavily_post_json(url: str, payload: Mapping[str, Any], api_key: str, *, timeout_seconds: int = 30) -> Mapping[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - explicit operator-run endpoint.
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Tavily request failed with HTTP {exc.code}: {detail[:500]}") from exc
    decoded = json.loads(raw)
    if not isinstance(decoded, Mapping):
        raise ValueError("Tavily response root is not an object")
    return decoded


def fake_search_payload(query: ProbeQuery) -> dict[str, Any]:
    slug = query.company_key.replace("_", "-") or "company"
    return {
        "query": query.query,
        "results": [
            {
                "title": f"{query.company_name} Careers",
                "url": f"https://www.{slug}.example/careers",
                "content": "Career page with jobs and remote work context.",
                "score": 0.91,
            },
            {
                "title": f"{query.company_name} Data Engineer Job",
                "url": f"https://jobs.{slug}.example/data-engineer",
                "content": "Data Engineer role with analytics and Germany context.",
                "score": 0.84,
            },
        ][: query.max_results],
    }


def extract_search_results(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []
    extracted: list[dict[str, str]] = []
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue
        url = _text(item.get("url"), default="")
        title = _text(item.get("title"), default="")
        if not url and not title:
            continue
        extracted.append({"url": url, "title": title})
    return extracted


def classify_evidence_hint(query: ProbeQuery, urls: Sequence[str], titles: Sequence[str]) -> str:
    return classify_evidence_hint_from_url_classes(classify_url_evidence_classes(query, urls, titles))


def classify_url_evidence_classes(
    query: ProbeQuery,
    urls: Sequence[str],
    titles: Sequence[str] = (),
) -> tuple[str, ...]:
    classes: list[str] = []
    for index, url in enumerate(urls):
        title = titles[index] if index < len(titles) else ""
        classes.append(classify_url_evidence(query, url, title))
    return tuple(classes)


def classify_url_evidence(query: ProbeQuery, url: str, title: str = "") -> str:
    host = _hostname(url)
    if not host:
        return "unrelated_or_generic_url"

    if _is_weak_market_or_aggregator_host(host):
        return "aggregator_or_market_url"

    path_text = _path_tokens(url)
    title_text = _normalize_token(title)
    combined_text = f"{_normalize_token(host)} {path_text} {title_text}"
    company_matches = _candidate_identity_matches(query, f"{host} {path_text} {title}")

    if _is_origin_provider_host(host):
        if not company_matches:
            return "unrelated_or_generic_url"
        if _has_detail_path([url]) or _has_role_hint(f"{path_text} {title}"):
            return "company_specific_job_detail_url"
        return "origin_provider_url"

    if company_matches:
        if _has_detail_path([url]) or _has_role_hint(f"{path_text} {title}"):
            return "company_specific_job_detail_url"
        if _has_career_path([url]) or _has_career_text(combined_text):
            return "company_origin_or_career_url"
        return "company_origin_or_career_url"

    return "unrelated_or_generic_url"


def classify_evidence_hint_from_url_classes(url_evidence_classes: Sequence[str]) -> str:
    if not url_evidence_classes:
        return "no_actionable_hint"
    if "company_specific_job_detail_url" in url_evidence_classes:
        return "company_specific_job_detail_hint_found"
    if any(item in {"company_origin_or_career_url", "origin_provider_url"} for item in url_evidence_classes):
        return "origin_or_career_hint_found"
    if "aggregator_or_market_url" in url_evidence_classes:
        return "weak_market_or_aggregator_hint_found"
    return "generic_web_hint_found"


def _candidate_identity(candidate: Mapping[str, Any]) -> tuple[str, str]:
    trial_id = _text(candidate.get("trial_id"), default="")
    if trial_id:
        return ("trial_id", trial_id.lower())
    company_key = _text(candidate.get("company_key"), default="")
    if company_key:
        return ("company_key", company_key.lower())
    company_name = _normalize_token(_text(candidate.get("company_name"), default="unknown_company"))
    return ("company_name", company_name)


def _is_provider_auth_failure(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("http 401", "unauthorized", "invalid api key", "authentication"))


def _is_company_specific_url(query: ProbeQuery, url: str) -> bool:
    return classify_url_evidence(query, url) in STRONG_URL_EVIDENCE_CLASSES


def _is_origin_provider_host(host: str) -> bool:
    return any(host == provider or host.endswith("." + provider) for provider in ORIGIN_PROVIDER_HOSTS)


def _candidate_identity_matches(query: ProbeQuery, text: str) -> bool:
    normalized_text = _normalize_token(text)
    tokens = _candidate_match_tokens(query)
    return any(token in normalized_text for token in tokens)


def _candidate_match_tokens(query: ProbeQuery) -> tuple[str, ...]:
    tokens: list[str] = []
    for raw in (query.company_key, query.company_name):
        for token in _company_tokens(raw):
            if token not in tokens:
                tokens.append(token)
    return tuple(tokens)


def _is_weak_market_or_aggregator_url(url: str) -> bool:
    return _is_weak_market_or_aggregator_host(_hostname(url))


def _is_weak_market_or_aggregator_host(host: str) -> bool:
    return any(host == weak or host.endswith("." + weak) for weak in WEAK_MARKET_OR_AGGREGATOR_HOSTS)


def _hostname(url: str) -> str:
    try:
        parsed = urlparse(url if "://" in url else "https://" + url)
    except ValueError:
        return ""
    return (parsed.hostname or "").lower().removeprefix("www.")


def _path_tokens(url: str) -> str:
    try:
        parsed = urlparse(url if "://" in url else "https://" + url)
    except ValueError:
        return ""
    return _normalize_token(parsed.path)


def _has_career_path(urls: Sequence[str]) -> bool:
    return any(any(token in _path_tokens(url) for token in CAREER_PATH_TOKENS) for url in urls)


def _has_detail_path(urls: Sequence[str]) -> bool:
    return any(any(token in _path_tokens(url) for token in ("data", "engineer", "analytics", "consultant")) for url in urls)


def _has_career_text(text: str) -> bool:
    normalized = _normalize_token(text)
    return any(token in normalized for token in CAREER_PATH_TOKENS)


def _has_role_hint(text: str) -> bool:
    normalized = _normalize_token(text)
    return any(token in normalized for token in ROLE_HINT_TOKENS)


def _company_tokens(value: str) -> tuple[str, ...]:
    normalized = _normalize_token(value)
    return tuple(
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in GENERIC_COMPANY_TOKEN_STOPWORDS
    )


def _normalize_token(value: str) -> str:
    text = str(value).lower()
    text = (
        text.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    text = unicodedata.normalize("NFKD", text)
    normalized: list[str] = []
    for char in text:
        normalized.append(char if char.isascii() and char.isalnum() else " ")
    return " ".join("".join(normalized).split())


def build_candidate_results(results: Sequence[ProbeResult]) -> list[dict[str, Any]]:
    grouped: dict[str, list[ProbeResult]] = defaultdict(list)
    for result in results:
        grouped[result.trial_id].append(result)
    output: list[dict[str, Any]] = []
    for trial_id, rows in grouped.items():
        hints = Counter(row.evidence_hint for row in rows)
        executed = sum(1 for row in rows if row.request_executed)
        completed = sum(1 for row in rows if row.status == "completed")
        first = rows[0]
        output.append(
            {
                "trial_id": trial_id,
                "company_key": first.company_key,
                "company_name": first.company_name,
                "probe_count": len(rows),
                "executed_request_count": executed,
                "completed_request_count": completed,
                "failed_request_count": sum(1 for row in rows if row.status == "request_failed"),
                "evidence_hints": dict(sorted(hints.items())),
                "trial_outcome": candidate_trial_outcome(rows),
                "allowed_next_step": "human_review_evidence_only",
                "candidate_creation_allowed": False,
                "gate_decision_allowed": False,
                "connector_activation_allowed": False,
            }
        )
    return sorted(output, key=lambda item: (str(item["trial_outcome"]), str(item["company_name"]).lower()))


def candidate_trial_outcome(rows: Sequence[ProbeResult]) -> str:
    if not rows:
        return "no_probe_rows"
    if all(not row.request_executed for row in rows):
        if any(row.evidence_hint == "blocked_after_provider_auth_failure" for row in rows):
            return "provider_auth_failed_requires_key_review"
        return "planned_not_executed"
    if any(row.evidence_hint in PROVIDER_AUTH_FAILURE_HINTS for row in rows):
        return "provider_auth_failed_requires_key_review"
    if any(row.evidence_hint in STRONG_EVIDENCE_HINTS for row in rows):
        return "external_hint_found_requires_human_review"
    if any(row.evidence_hint in WEAK_EVIDENCE_HINTS for row in rows):
        return "weak_external_hint_requires_human_review"
    if any(row.status == "request_failed" for row in rows):
        return "probe_error_requires_retry_or_review"
    return "no_useful_external_hint_found"

def build_summary(
    manifest: Sequence[ProbeQuery],
    results: Sequence[ProbeResult],
    *,
    manifest_diagnostics: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    diagnostics = dict(manifest_diagnostics or {})
    strong_hint_trial_ids = {result.trial_id for result in results if result.evidence_hint in STRONG_EVIDENCE_HINTS}
    weak_hint_trial_ids = {result.trial_id for result in results if result.evidence_hint in WEAK_EVIDENCE_HINTS}
    provider_auth_trial_ids = {result.trial_id for result in results if result.evidence_hint in PROVIDER_AUTH_FAILURE_HINTS}
    strong_url_count = sum(
        1 for result in results for url_class in result.url_evidence_classes if url_class in STRONG_URL_EVIDENCE_CLASSES
    )
    weak_url_count = sum(
        1 for result in results for url_class in result.url_evidence_classes if url_class == "aggregator_or_market_url"
    )
    generic_url_count = sum(
        1 for result in results for url_class in result.url_evidence_classes if url_class == "unrelated_or_generic_url"
    )
    origin_url_trial_ids = {
        result.trial_id
        for result in results
        if any(
            url_class in {"company_origin_or_career_url", "origin_provider_url"}
            for url_class in result.url_evidence_classes
        )
    }
    job_detail_url_trial_ids = {
        result.trial_id
        for result in results
        if "company_specific_job_detail_url" in result.url_evidence_classes
    }
    return {
        "planned_probe_count": len(manifest),
        "external_requests_executed_count": sum(1 for result in results if result.request_executed),
        "completed_probe_count": sum(1 for result in results if result.status == "completed"),
        "failed_probe_count": sum(1 for result in results if result.status == "request_failed"),
        "blocked_after_provider_auth_failure_count": sum(
            1 for result in results if result.status == "blocked_after_provider_auth_failure"
        ),
        "candidate_count": len({query.trial_id for query in manifest}),
        "candidate_with_external_hint_count": len(strong_hint_trial_ids),
        "candidate_with_weak_external_hint_count": len(weak_hint_trial_ids - strong_hint_trial_ids),
        "candidate_with_provider_auth_failure_count": len(provider_auth_trial_ids),
        "strong_url_count": strong_url_count,
        "weak_url_count": weak_url_count,
        "generic_url_count": generic_url_count,
        "candidate_with_strong_origin_hint_count": len(origin_url_trial_ids),
        "candidate_with_company_specific_job_detail_hint_count": len(job_detail_url_trial_ids),
        "duplicate_candidate_count": int(diagnostics.get("duplicate_candidate_count", 0)),
        "duplicate_probe_count": int(diagnostics.get("duplicate_probe_count", 0)),
        "candidate_creation_count": 0,
        "gate_decision_count": 0,
        "connector_activation_count": 0,
        "database_write_count": 0,
    }

def empty_summary() -> dict[str, int]:
    return {
        "planned_probe_count": 0,
        "external_requests_executed_count": 0,
        "completed_probe_count": 0,
        "failed_probe_count": 0,
        "blocked_after_provider_auth_failure_count": 0,
        "candidate_count": 0,
        "candidate_with_external_hint_count": 0,
        "candidate_with_weak_external_hint_count": 0,
        "candidate_with_provider_auth_failure_count": 0,
        "strong_url_count": 0,
        "weak_url_count": 0,
        "generic_url_count": 0,
        "candidate_with_strong_origin_hint_count": 0,
        "candidate_with_company_specific_job_detail_hint_count": 0,
        "duplicate_candidate_count": 0,
        "duplicate_probe_count": 0,
        "candidate_creation_count": 0,
        "gate_decision_count": 0,
        "connector_activation_count": 0,
        "database_write_count": 0,
    }

def build_run_policy(
    *,
    execute_external_probes: bool,
    provider: str,
    max_candidates: int | None = 200,
    max_queries_per_candidate: int = 2,
    max_results_per_query: int = 5,
    max_total_requests: int = 500,
) -> dict[str, Any]:
    return {
        "execute_external_probes": bool(execute_external_probes),
        "provider": provider,
        "max_candidates": max_candidates,
        "max_queries_per_candidate": max_queries_per_candidate,
        "max_results_per_query": max_results_per_query,
        "max_total_requests": max_total_requests,
        "allowed_artifact_actions": list(ALLOWED_ARTIFACT_ACTIONS),
        "explicitly_disallowed_actions": list(DISALLOWED_ACTIONS),
        "no_mutation_boundary": NO_MUTATION_BOUNDARY,
    }


def mutation_counts(*, external_requests: int) -> dict[str, int]:
    return {
        "created_candidates": 0,
        "automatic_candidate_promotions": 0,
        "written_gate_decisions": 0,
        "activated_connectors": 0,
        "scheduler_changes": 0,
        "bronze_silver_gold_writes": 0,
        "database_writes": 0,
        "external_requests_executed_by_this_command": external_requests,
    }


def load_trial_plan(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object.")
    schema_version = str(payload.get("schema_version") or "")
    if not schema_version.startswith(INPUT_SCHEMA_PREFIX):
        raise ValueError(f"Unexpected input schema_version: {schema_version or '<missing>'}")
    return payload


def write_outputs(report: Mapping[str, Any], export_dir: Path) -> dict[str, str]:
    export_dir.mkdir(parents=True, exist_ok=True)
    json_path = export_dir / "expand002_controlled_external_probe_trial_run.json"
    csv_path = export_dir / "expand002_controlled_external_probe_trial_results.csv"
    md_path = export_dir / "expand002_controlled_external_probe_trial_run.md"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    write_probe_results_csv(csv_path, report.get("probe_results", []))
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def write_probe_results_csv(path: Path, probe_results: Any) -> None:
    fieldnames = [
        "probe_id",
        "trial_id",
        "company_key",
        "company_name",
        "stage",
        "provider",
        "status",
        "request_executed",
        "result_count",
        "evidence_hint",
        "query",
        "urls",
        "url_evidence_classes",
        "error",
    ]
    rows = _ensure_mapping_list(probe_results)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: "; ".join(str(v) for v in row.get(key, []))
                    if key in {"urls", "url_evidence_classes"} and isinstance(row.get(key), list)
                    else row.get(key, "")
                    for key in fieldnames
                }
            )


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), Mapping) else {}
    policy = report.get("run_policy", {}) if isinstance(report.get("run_policy"), Mapping) else {}
    candidates = _ensure_mapping_list(report.get("candidate_results"))[:30]
    lines: list[str] = []
    lines.append("# EXPAND-002 Controlled External Probe Trial Run")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append(
        "Controlled external evidence collection only. Results are review artifacts and do not create candidates, "
        "write gate decisions, activate connectors, mutate Bronze/Silver/Gold, write DB state, or change scheduler behavior."
    )
    lines.append("")
    if report.get("input_warning"):
        lines.append("## Input Warning")
        lines.append("")
        lines.append(str(report.get("input_warning")))
        lines.append("")
    lines.append("## Run Policy")
    lines.append("")
    lines.append(f"- Execute external probes: {policy.get('execute_external_probes', False)}")
    lines.append(f"- Provider: {policy.get('provider', 'dry_run')}")
    lines.append(f"- Max candidates: {policy.get('max_candidates')}")
    lines.append(f"- Max total requests: {policy.get('max_total_requests')}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Planned probes: {summary.get('planned_probe_count', 0)}")
    lines.append(f"- External requests executed: {summary.get('external_requests_executed_count', 0)}")
    lines.append(f"- Completed probes: {summary.get('completed_probe_count', 0)}")
    lines.append(f"- Failed probes: {summary.get('failed_probe_count', 0)}")
    lines.append(f"- Candidates with actionable external hint: {summary.get('candidate_with_external_hint_count', 0)}")
    lines.append(f"- Candidates with weak external hint: {summary.get('candidate_with_weak_external_hint_count', 0)}")
    lines.append(f"- Provider-auth blocked probes: {summary.get('blocked_after_provider_auth_failure_count', 0)}")
    lines.append(f"- Strong URL evidence count: {summary.get('strong_url_count', 0)}")
    lines.append(f"- Weak URL evidence count: {summary.get('weak_url_count', 0)}")
    lines.append(f"- Generic URL evidence count: {summary.get('generic_url_count', 0)}")
    lines.append(f"- Candidates with strong origin hint: {summary.get('candidate_with_strong_origin_hint_count', 0)}")
    lines.append(f"- Candidates with company-specific job detail hint: {summary.get('candidate_with_company_specific_job_detail_hint_count', 0)}")
    lines.append(f"- Duplicate candidates removed: {summary.get('duplicate_candidate_count', 0)}")
    lines.append(f"- Duplicate probes removed: {summary.get('duplicate_probe_count', 0)}")
    lines.append(f"- Created candidates: {summary.get('candidate_creation_count', 0)}")
    lines.append(f"- Gate decisions: {summary.get('gate_decision_count', 0)}")
    lines.append(f"- Connector activations: {summary.get('connector_activation_count', 0)}")
    lines.append("")
    lines.append("## Candidate Outcomes")
    lines.append("")
    if not candidates:
        lines.append("No candidate outcomes available.")
    else:
        lines.append("| Company | Outcome | Probes | Executed | Hints |")
        lines.append("| --- | --- | ---: | ---: | --- |")
        for item in candidates:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(item.get("company_name")),
                        _md_cell(item.get("trial_outcome")),
                        str(item.get("probe_count", 0)),
                        str(item.get("executed_request_count", 0)),
                        _md_cell(json.dumps(item.get("evidence_hints", {}), sort_keys=True)),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def _clip_query(query: str) -> str:
    return " ".join(query.split())[:390]


def _ensure_mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text(value: Any, *, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
