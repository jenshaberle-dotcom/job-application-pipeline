"""Post-process an origin-provider benchmark with hard evidence and optional LLM review.

The command consumes an immutable benchmark artifact. It performs bounded public
HTTPS reads only and writes a review artifact/checkpoint. It never mutates the
Pipeline database, candidate URLs, connectors, sources, Bronze/Silver or scheduler.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urljoin, urlparse

import requests

from src.search_intelligence.origin_llm_adjudication import (
    LLMAdjudicationResult,
    adjudicate_with_openai,
    final_review_state,
)
from src.search_intelligence.origin_source_evidence import (
    ArtifactCandidate,
    OriginEvidenceAssessment,
    OriginEvidenceDecision,
    assess_origin_evidence_candidate,
    decide_origin_evidence,
    failed_page_evidence,
    page_evidence_from_html,
    resolves_to_public_addresses,
    should_request_llm_adjudication,
    validate_public_https_url,
)
from src.search_intelligence.origin_source_discovery import is_known_aggregator_domain
from src.search_intelligence.origin_source_discovery_agent import normalize_candidate_url

REPORT_SCHEMA_VERSION = "origin_evidence_adjudication.v1"
CHECKPOINT_SCHEMA_VERSION = "origin_evidence_adjudication_checkpoint.v1"
USER_AGENT = "job-application-pipeline-origin-evidence/0.1 (+bounded review-only runtime)"
BOUNDARY = (
    "benchmark_artifact_input_only",
    "bounded_public_https_reads",
    "llm_review_signal_only",
    "no_candidate_url_write",
    "no_connector_registration",
    "no_source_activation",
    "no_bronze_silver_write",
    "no_scheduler_change",
)


class HttpBudget:
    def __init__(self, maximum: int) -> None:
        if maximum < 0:
            raise ValueError("max-http-requests must not be negative")
        self.maximum = maximum
        self.attempts = 0

    def consume(self) -> bool:
        if self.attempts >= self.maximum:
            return False
        self.attempts += 1
        return True


def write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _artifact_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_fetch(
    url: str,
    *,
    timeout_seconds: float,
    max_response_bytes: int,
    budget: HttpBudget,
    session: requests.Session,
):
    current = normalize_candidate_url(url)
    if current is None:
        return failed_page_evidence(url, "invalid_url")
    for _redirect in range(5):
        valid, failure = validate_public_https_url(current)
        if not valid:
            return failed_page_evidence(current, failure or "url_policy_rejected")
        host = str(urlparse(current).hostname or "")
        public, dns_failure = resolves_to_public_addresses(host)
        if not public:
            return failed_page_evidence(current, dns_failure or "dns_policy_rejected")
        if not budget.consume():
            return failed_page_evidence(current, "http_request_budget_exhausted")
        try:
            response = session.get(
                current,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.2",
                },
                timeout=timeout_seconds,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            return failed_page_evidence(current, type(exc).__name__)
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                return failed_page_evidence(current, "redirect_without_location")
            current = urljoin(current, location)
            continue
        chunks: list[bytes] = []
        size = 0
        try:
            for chunk in response.iter_content(chunk_size=16_384):
                if not chunk:
                    continue
                remaining = max_response_bytes - size
                if remaining <= 0:
                    break
                chunks.append(chunk[:remaining])
                size += min(len(chunk), remaining)
                if size >= max_response_bytes:
                    break
            encoding = response.encoding or "utf-8"
            body = b"".join(chunks).decode(encoding, errors="replace")
            return page_evidence_from_html(
                requested_url=url,
                final_url=current,
                status_code=int(response.status_code),
                body=body,
            )
        finally:
            response.close()
    return failed_page_evidence(current, "redirect_limit_exceeded")


def _candidate_from_mapping(raw: Mapping[str, object]) -> ArtifactCandidate | None:
    normalized = normalize_candidate_url(str(raw.get("final_url") or raw.get("url") or ""))
    if normalized is None:
        return None
    probe = raw.get("probe")
    probe_map = probe if isinstance(probe, Mapping) else {}
    return ArtifactCandidate(
        url=normalized,
        provider=str(raw.get("provider") or raw.get("search_provider") or "unknown"),
        provider_reason=str(raw.get("provider_reason") or ""),
        title=str(raw.get("title") or probe_map.get("title") or ""),
        snippet=str(raw.get("snippet") or ""),
        prior_decision=str(raw.get("decision") or ""),
        prior_identity_score=float(raw.get("identity_score") or 0.0),
        prior_total_score=float(raw.get("total_score") or 0.0),
        prior_reachable=(
            bool(probe_map.get("reachable")) if "reachable" in probe_map else None
        ),
    )


def collect_artifact_candidates(
    result: Mapping[str, object],
    *,
    maximum: int,
) -> tuple[ArtifactCandidate, ...]:
    raw_items: list[Mapping[str, object]] = []
    for field in ("alternatives", "rejected", "search_results"):
        values = result.get(field)
        if isinstance(values, list):
            raw_items.extend(item for item in values if isinstance(item, Mapping))
    selected_url = str(result.get("selected_url") or "").strip()
    if selected_url:
        raw_items.insert(
            0,
            {
                "url": selected_url,
                "provider": "previous_deterministic_selection",
                "decision": "select_candidate",
                "identity_score": result.get("confidence_score") or 0.0,
                "total_score": result.get("confidence_score") or 0.0,
            },
        )

    by_url: dict[str, ArtifactCandidate] = {}
    for raw in raw_items:
        candidate = _candidate_from_mapping(raw)
        if candidate is None:
            continue
        host = str(urlparse(candidate.url).hostname or "")
        if is_known_aggregator_domain(host):
            continue
        existing = by_url.get(candidate.url)
        if existing is None:
            by_url[candidate.url] = candidate
            continue
        candidate_rank = (candidate.prior_identity_score, candidate.prior_total_score)
        existing_rank = (existing.prior_identity_score, existing.prior_total_score)
        stronger = candidate if candidate_rank > existing_rank else existing
        other = existing if stronger is candidate else candidate
        titles = [item for item in (stronger.title, other.title) if item]
        snippets = [item for item in (stronger.snippet, other.snippet) if item]
        by_url[candidate.url] = ArtifactCandidate(
            url=candidate.url,
            provider=stronger.provider,
            provider_reason=stronger.provider_reason or other.provider_reason,
            title=" | ".join(dict.fromkeys(titles)),
            snippet=" | ".join(dict.fromkeys(snippets)),
            prior_decision=stronger.prior_decision or other.prior_decision,
            prior_identity_score=max(
                candidate.prior_identity_score, existing.prior_identity_score
            ),
            prior_total_score=max(candidate.prior_total_score, existing.prior_total_score),
            prior_reachable=(
                stronger.prior_reachable
                if stronger.prior_reachable is not None
                else other.prior_reachable
            ),
        )

    ordered = sorted(
        by_url.values(),
        key=lambda item: (
            item.prior_decision != "select_candidate",
            -item.prior_identity_score,
            -item.prior_total_score,
            item.url,
        ),
    )
    return tuple(ordered[:maximum])


def _decision_from_json(payload: Mapping[str, object]) -> OriginEvidenceDecision:
    assessments = tuple(
        OriginEvidenceAssessment(
            **{
                **dict(item),
                "sample_job_urls": tuple(item.get("sample_job_urls") or ()),
                "reasons": tuple(item.get("reasons") or ()),
            }
        )
        for item in payload.get("assessments", [])
        if isinstance(item, Mapping)
    )
    return OriginEvidenceDecision(
        company_key=str(payload["company_key"]),
        company_name=str(payload["company_name"]),
        deterministic_decision=str(payload["deterministic_decision"]),
        selected_candidate_id=(
            None
            if payload.get("selected_candidate_id") is None
            else str(payload["selected_candidate_id"])
        ),
        selected_url=None if payload.get("selected_url") is None else str(payload["selected_url"]),
        confidence_score=float(payload["confidence_score"]),
        confidence_band=str(payload["confidence_band"]),
        selection_margin=float(payload["selection_margin"]),
        manual_review_required=bool(payload["manual_review_required"]),
        adjudication_reasons=tuple(payload.get("adjudication_reasons") or ()),
        assessments=assessments,
    )


def _load_checkpoint(
    path: Path | None,
    *,
    artifact_sha256: str,
    company_keys: Sequence[str],
    config: Mapping[str, object],
) -> tuple[list[dict[str, object]], int]:
    if path is None or not path.exists():
        return [], 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise SystemExit("invalid evidence checkpoint root")
    if payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise SystemExit("unsupported evidence checkpoint schema")
    if payload.get("artifact_sha256") != artifact_sha256:
        raise SystemExit("evidence checkpoint input artifact mismatch")
    if payload.get("company_keys") != list(company_keys):
        raise SystemExit("evidence checkpoint company ordering mismatch")
    if payload.get("config") != dict(config):
        raise SystemExit("evidence checkpoint configuration mismatch")
    results = payload.get("results")
    if not isinstance(results, list) or not all(isinstance(item, dict) for item in results):
        raise SystemExit("evidence checkpoint results must be objects")
    completed = [str(item.get("company_key") or "") for item in results]
    if completed != list(company_keys[: len(completed)]):
        raise SystemExit("evidence checkpoint is not an ordered company prefix")
    llm_attempts = int(payload.get("llm_request_attempts") or 0)
    return [dict(item) for item in results], llm_attempts


def _write_checkpoint(
    path: Path | None,
    *,
    artifact_sha256: str,
    company_keys: Sequence[str],
    config: Mapping[str, object],
    results: Sequence[Mapping[str, object]],
    llm_request_attempts: int,
    complete: bool,
) -> None:
    if path is None:
        return
    write_json_atomic(
        path,
        {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "artifact_sha256": artifact_sha256,
            "company_keys": list(company_keys),
            "config": dict(config),
            "llm_request_attempts": llm_request_attempts,
            "complete": complete,
            "results": list(results),
            "boundary": list(BOUNDARY),
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Grade origin candidates and optionally adjudicate ambiguous cases."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--target-location", default="Hannover")
    parser.add_argument("--target-locale", default="de")
    parser.add_argument("--max-candidates-per-company", type=int, default=3)
    parser.add_argument("--max-http-requests", type=int, default=30)
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--max-response-bytes", type=int, default=750_000)
    parser.add_argument("--enable-llm-adjudication", action="store_true")
    parser.add_argument("--max-llm-requests", type=int, default=2)
    parser.add_argument("--llm-model", default=os.getenv("ORIGIN_ADJUDICATION_MODEL", ""))
    parser.add_argument("--openai-api-key", default=os.getenv("OPENAI_API_KEY", ""))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.max_candidates_per_company < 1:
        raise SystemExit("max-candidates-per-company must be at least 1")
    if args.max_llm_requests < 0:
        raise SystemExit("max-llm-requests must not be negative")
    if args.enable_llm_adjudication and not str(args.openai_api_key or "").strip():
        raise SystemExit("LLM adjudication enabled but OPENAI_API_KEY is missing")
    if args.enable_llm_adjudication and not str(args.llm_model or "").strip():
        raise SystemExit("LLM adjudication enabled but --llm-model is missing")

    benchmark = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(benchmark, Mapping):
        raise SystemExit("benchmark artifact root must be an object")
    raw_results = benchmark.get("results")
    if not isinstance(raw_results, list) or not all(isinstance(item, Mapping) for item in raw_results):
        raise SystemExit("benchmark results must be an array of objects")
    company_keys = [str(item.get("company_key") or "") for item in raw_results]
    if not all(company_keys) or len(company_keys) != len(set(company_keys)):
        raise SystemExit("benchmark company keys must be unique and non-empty")

    config = {
        "target_location": args.target_location,
        "target_locale": args.target_locale,
        "max_candidates_per_company": args.max_candidates_per_company,
        "max_http_requests": args.max_http_requests,
        "max_response_bytes": args.max_response_bytes,
        "llm_enabled": args.enable_llm_adjudication,
        "max_llm_requests": args.max_llm_requests,
        "llm_model": args.llm_model if args.enable_llm_adjudication else None,
    }
    artifact_sha = _artifact_sha256(args.input)
    results, llm_attempts = _load_checkpoint(
        args.checkpoint,
        artifact_sha256=artifact_sha,
        company_keys=company_keys,
        config=config,
    )
    resumed_count = len(results)
    http_budget = HttpBudget(args.max_http_requests)
    session = requests.Session()

    for raw in raw_results[len(results) :]:
        company_key = str(raw["company_key"])
        company_name = str(raw.get("company_name") or company_key)
        candidates = collect_artifact_candidates(
            raw,
            maximum=args.max_candidates_per_company,
        )
        assessments: list[OriginEvidenceAssessment] = []
        for index, candidate in enumerate(candidates, start=1):
            page = _safe_fetch(
                candidate.url,
                timeout_seconds=args.timeout_seconds,
                max_response_bytes=args.max_response_bytes,
                budget=http_budget,
                session=session,
            )
            assessments.append(
                assess_origin_evidence_candidate(
                    candidate_id=f"C{index}",
                    candidate=candidate,
                    company_key=company_key,
                    company_name=company_name,
                    page=page,
                    target_location=args.target_location,
                    target_locale=args.target_locale,
                )
            )

        decision = decide_origin_evidence(
            company_key=company_key,
            company_name=company_name,
            assessments=assessments,
        )
        llm_result: LLMAdjudicationResult | None = None
        llm_eligible = should_request_llm_adjudication(decision)
        if (
            args.enable_llm_adjudication
            and llm_eligible
            and llm_attempts < args.max_llm_requests
        ):
            llm_attempts += 1
            llm_result = adjudicate_with_openai(
                decision,
                api_key=args.openai_api_key,
                model=args.llm_model,
            )

        result_payload = decision.to_json()
        result_payload.update(
            {
                "llm_eligible": llm_eligible,
                "provider_adjudication": None
                if llm_result is None
                else llm_result.to_json(),
                "final_review_state": final_review_state(decision, llm_result),
                "review_output_only_not_pipeline_input": True,
            }
        )
        results.append(result_payload)
        _write_checkpoint(
            args.checkpoint,
            artifact_sha256=artifact_sha,
            company_keys=company_keys,
            config=config,
            results=results,
            llm_request_attempts=llm_attempts,
            complete=False,
        )

    deterministic_selected = sum(
        item.get("deterministic_decision") == "origin_url_candidate_selected"
        for item in results
    )
    manual_review = sum(bool(item.get("manual_review_required")) for item in results)
    llm_eligible_count = sum(bool(item.get("llm_eligible")) for item in results)
    llm_completed = sum(
        isinstance(item.get("provider_adjudication"), Mapping)
        and item["provider_adjudication"].get("status") == "completed"
        for item in results
    )
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "source_benchmark_schema_version": benchmark.get("schema_version"),
        "source_artifact_sha256": artifact_sha,
        "projection_fingerprint": (
            benchmark.get("projection", {}).get("fingerprint")
            if isinstance(benchmark.get("projection"), Mapping)
            else None
        ),
        "review_output_only_not_pipeline_input": True,
        "boundary": list(BOUNDARY),
        "config": config,
        "recovery": {
            "checkpoint_enabled": args.checkpoint is not None,
            "resumed_result_count": resumed_count,
        },
        "summary": {
            "company_count": len(results),
            "deterministic_selected_count": deterministic_selected,
            "manual_review_count": manual_review,
            "llm_eligible_count": llm_eligible_count,
            "llm_request_attempts": llm_attempts,
            "llm_completed_count": llm_completed,
            "http_request_attempts": http_budget.attempts,
        },
        "results": results,
    }
    write_json_atomic(args.output, report)
    _write_checkpoint(
        args.checkpoint,
        artifact_sha256=artifact_sha,
        company_keys=company_keys,
        config=config,
        results=results,
        llm_request_attempts=llm_attempts,
        complete=True,
    )
    print(
        "origin_evidence_adjudication_complete: "
        f"companies={len(results)} "
        f"deterministic_selected={deterministic_selected} "
        f"manual_review={manual_review} "
        f"llm_eligible={llm_eligible_count} "
        f"llm_attempts={llm_attempts} "
        f"http_attempts={http_budget.attempts} "
        f"output={args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
