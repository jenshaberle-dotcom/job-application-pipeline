"""Run one bounded LLM-BOOST-001 Detail Semantics booster.

The command fetches exactly one public HTTPS detail page with the existing
DETAIL-001 HTTP helper, extracts bounded plain text without persisting raw HTML,
runs deterministic semantic extraction first, and only then permits the
canonical Luna -> Terra -> Sol -> Luna-max semantic hypothesis cascade for the
explicitly requested missing fields.

Every live model hypothesis must already have passed exact same-text span
verification in the provider adapter. This runner rechecks those spans before
accepting them as grounded semantic evidence. Grounded semantic evidence remains
hypothesis/evidence only: no database, gate, lifecycle, ranking, application or
product write path exists here and product authority stays false.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from typing import Mapping, Sequence
from urllib.parse import urlparse

import requests

from scripts.run_employer_origin_detail_evidence_repair_agent import (
    TextExtractor,
    fetch_url,
)
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.search_intelligence.detail_semantics_booster_execution import (
    DetailSemanticsHypothesisObservation,
    DetailSemanticsValidationObservation,
    execute_detail_semantics_booster,
)
from src.search_intelligence.detail_semantics_deterministic import (
    deterministic_detail_semantics,
)
from src.search_intelligence.detail_semantics_gap import (
    SEMANTIC_FIELD_NAMES,
    SemanticEvidenceReference,
    analyze_detail_semantics_gap,
)
from src.search_intelligence.detail_semantics_hypothesis_provider import (
    MAX_DETAIL_TEXT_CHARS,
    request_detail_semantics_hypotheses,
)
from src.search_intelligence.llm_booster_policy import (
    HARD_COST_CEILING_USD,
    MODEL_CONFIG,
    BoosterStage,
    TavilyState,
)
from src.search_intelligence.multi_origin_evidence import same_base_domain
from src.search_intelligence.origin_llm_model_campaign_types import (
    MODEL_PRICES_USD_PER_MILLION,
)
from src.search_intelligence.relevance_evidence_probe import relevance_signals

RESULT = "DETAIL_SEMANTICS_BOOSTER_COMPLETED"

ROLE_TERMS = (
    "data engineer",
    "analytics engineer",
    "data analyst",
    "business analyst",
    "software engineer",
    "software developer",
    "machine learning engineer",
    "ml engineer",
    "product owner",
)
SENIORITY_TERMS = ("junior", "senior", "lead", "principal", "staff")
SKILL_TERMS = (
    "python",
    "sql",
    "databricks",
    "spark",
    "pyspark",
    "azure",
    "aws",
    "gcp",
    "power bi",
    "tableau",
    "snowflake",
    "dbt",
)
REMOTE_TERMS = (
    "remote",
    "hybrid",
    "homeoffice",
    "home office",
    "mobiles arbeiten",
    "mobile work",
)
WIDE_LOCATION_TERMS = ("deutschland", "germany", "bundesweit", "deutschlandweit")


def _missing_secret(value: str | None) -> bool:
    text = str(value or "").strip()
    lowered = text.lower()
    return (
        not text
        or text == "..."
        or text in {"<YOUR_API_KEY>", "YOUR_API_KEY", "changeme"}
        or "your_api_key" in lowered
        or "realer_key" in lowered
    )


def _reserved_cost_usd(
    *, model: str, reserved_input_tokens: int, max_output_tokens: int
) -> float | None:
    prices = MODEL_PRICES_USD_PER_MILLION.get(model)
    if prices is None:
        return None
    input_price, output_price = prices
    return (
        reserved_input_tokens * input_price / 1_000_000
        + max_output_tokens * output_price / 1_000_000
    )


def _blocked_observation(
    *, stage: BoosterStage, status: str, message: str
) -> DetailSemanticsHypothesisObservation:
    model, _reasoning = MODEL_CONFIG[stage]
    return DetailSemanticsHypothesisObservation(
        status=status,
        request_attempted=False,
        semantic_fields={},
        evidence_references=(),
        model=model,
        response_id=None,
        estimated_cost_usd=0.0,
        rationale=message[:700],
        product_authority=False,
    )


def _requested_fields(values: Sequence[str] | None) -> tuple[str, ...]:
    if not values:
        return SEMANTIC_FIELD_NAMES
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        field = str(value or "").strip().lower()
        if field not in SEMANTIC_FIELD_NAMES:
            raise SystemExit(f"unsupported semantic field: {field or '<empty>'}")
        if field not in seen:
            seen.add(field)
            result.append(field)
    return tuple(result)


def _find_exact_reference(
    *, field: str, term: str, text: str, detail_url: str
) -> SemanticEvidenceReference | None:
    match = re.search(re.escape(term), text, flags=re.IGNORECASE)
    if match is None:
        return None
    evidence = text[match.start() : match.end()]
    return SemanticEvidenceReference(
        field=field,
        source_url=detail_url,
        evidence=evidence,
        value=evidence,
        span_start=match.start(),
        span_end=match.end(),
    )


def _deterministic_semantics(
    *,
    text: str,
    detail_url: str,
    target_location: str,
    requested_fields: tuple[str, ...],
) -> tuple[dict[str, object], tuple[SemanticEvidenceReference, ...]]:
    """Legacy lexical helper retained temporarily for regression compatibility."""
    fields: dict[str, object] = {}
    references: list[SemanticEvidenceReference] = []

    def first(field: str, terms: Sequence[str]) -> None:
        for term in terms:
            reference = _find_exact_reference(
                field=field,
                term=term,
                text=text,
                detail_url=detail_url,
            )
            if reference is None:
                continue
            fields[field] = reference.value
            references.append(reference)
            return

    if "role" in requested_fields:
        first("role", ROLE_TERMS)
    if "seniority" in requested_fields:
        first("seniority", SENIORITY_TERMS)
    if "skills" in requested_fields:
        skill_values: list[str] = []
        for term in SKILL_TERMS:
            reference = _find_exact_reference(
                field="skills",
                term=term,
                text=text,
                detail_url=detail_url,
            )
            if reference is None or reference.value is None:
                continue
            if reference.value not in skill_values:
                skill_values.append(reference.value)
                references.append(reference)
        if skill_values:
            fields["skills"] = tuple(skill_values)
    if "location" in requested_fields:
        location_terms = tuple(
            item
            for item in (target_location, *WIDE_LOCATION_TERMS)
            if str(item or "").strip()
        )
        first("location", location_terms)
    if "remote" in requested_fields:
        first("remote", REMOTE_TERMS)

    return fields, tuple(references)


def _references_ground_fields(
    *,
    detail_url: str,
    detail_text: str,
    semantic_fields: Mapping[str, object],
    references: tuple[SemanticEvidenceReference, ...],
) -> bool:
    by_field: dict[str, list[SemanticEvidenceReference]] = {}
    for reference in references:
        if reference.field not in SEMANTIC_FIELD_NAMES:
            return False
        if reference.source_url != detail_url:
            return False
        if reference.span_start is None or reference.span_end is None:
            return False
        if (
            reference.span_start < 0
            or reference.span_end <= reference.span_start
            or reference.span_end > len(detail_text)
        ):
            return False
        if detail_text[reference.span_start : reference.span_end] != reference.evidence:
            return False
        if not reference.value or reference.value.casefold() not in reference.evidence.casefold():
            return False
        by_field.setdefault(reference.field, []).append(reference)

    for field, raw_value in semantic_fields.items():
        field_name = str(field).strip().lower()
        field_references = by_field.get(field_name, [])
        if not field_references:
            return False
        if field_name == "skills":
            values = raw_value if isinstance(raw_value, (list, tuple)) else (raw_value,)
            for value in values:
                normalized = str(value or "").strip().casefold()
                if not normalized or not any(
                    normalized == str(item.value or "").strip().casefold()
                    for item in field_references
                ):
                    return False
        else:
            normalized = str(raw_value or "").strip().casefold()
            if not normalized or not any(
                normalized == str(item.value or "").strip().casefold()
                for item in field_references
            ):
                return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run bounded LLM-BOOST-001 Detail Semantics booster."
    )
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--detail-url", required=True)
    parser.add_argument("--target-location", default="hannover")
    parser.add_argument("--source-target", default="hannover")
    parser.add_argument(
        "--semantic-field",
        action="append",
        choices=SEMANTIC_FIELD_NAMES,
        help="Repeat to bound semantic scope. Defaults to all canonical fields.",
    )
    parser.add_argument("--disable-llm", action="store_true")
    parser.add_argument("--model-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--reserved-input-tokens", type=int, default=2500)
    parser.add_argument("--model-max-output-tokens", type=int, default=700)
    parser.add_argument("--luna-max-output-tokens", type=int, default=1200)
    parser.add_argument("--previous-semantic-fingerprint", default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    parsed = urlparse(str(args.detail_url or ""))
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("--detail-url must be a public HTTPS URL")
    if args.reserved_input_tokens < 1:
        raise SystemExit("--reserved-input-tokens must be positive")
    if args.model_max_output_tokens < 1 or args.luna_max_output_tokens < 1:
        raise SystemExit("model output token bounds must be positive")
    if args.model_timeout_seconds <= 0:
        raise SystemExit("--model-timeout-seconds must be positive")


def _fetch_failure_payload(
    *, args: argparse.Namespace, requested_fields: tuple[str, ...], message: str
) -> dict[str, object]:
    return {
        "schema_version": "detail_semantics_booster.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "result": "DETAIL_SEMANTICS_FETCH_FAILED",
        "company_name": args.company_name,
        "detail_url": args.detail_url,
        "requested_semantic_fields": list(requested_fields),
        "failure_reason": message[:500],
        "provider_requests": 0,
        "llm_requests": 0,
        "database_writes": 0,
        "gate_writes": 0,
        "product_writes": 0,
        "semantic_authority": False,
        "product_authority": False,
        "raw_html_persisted": False,
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    _validate_args(args)
    requested_fields = _requested_fields(args.semantic_field)
    openai_key = str(os.getenv("OPENAI_API_KEY") or "").strip()

    try:
        html, final_url, status_code = fetch_url(args.detail_url)
    except requests.RequestException as exc:
        return _fetch_failure_payload(
            args=args,
            requested_fields=requested_fields,
            message=f"{type(exc).__name__}: {' '.join(str(exc).split())}",
        )

    if not same_base_domain(args.detail_url, final_url):
        return _fetch_failure_payload(
            args=args,
            requested_fields=requested_fields,
            message="detail fetch redirected outside the original base domain",
        )

    extractor = TextExtractor()
    extractor.feed(html)
    detail_text = extractor.text[:MAX_DETAIL_TEXT_CHARS]
    if not detail_text:
        return _fetch_failure_payload(
            args=args,
            requested_fields=requested_fields,
            message="bounded detail text is empty",
        )

    signals = relevance_signals(
        detail_text,
        target_location=args.target_location,
        source_target=args.source_target,
    )
    profile_contract_satisfied = signals.has_profile_evidence
    geography_contract_satisfied = signals.has_target_or_remote_evidence
    detail_supported = bool(
        200 <= status_code < 400
        and profile_contract_satisfied
        and geography_contract_satisfied
    )
    deterministic_fields, deterministic_references = deterministic_detail_semantics(
        html=html,
        text=detail_text,
        page_title=extractor.title,
        detail_url=final_url,
        target_location=args.target_location,
        requested_fields=requested_fields,
    )
    gap = analyze_detail_semantics_gap(
        candidate_id=1,
        company_key=re.sub(r"[^a-z0-9]+", "-", args.company_name.casefold()).strip("-")
        or "detail-semantics-shadow",
        detail_url=final_url,
        deterministic_attempted=True,
        detail_supported=detail_supported,
        profile_contract_satisfied=profile_contract_satisfied,
        geography_contract_satisfied=geography_contract_satisfied,
        requested_semantic_fields=requested_fields,
        deterministic_semantic_fields=deterministic_fields,
        evidence_references=tuple(
            reference.to_json() for reference in deterministic_references
        ),
        tavily_state=TavilyState.DISABLED,
        previous_semantic_fingerprint=args.previous_semantic_fingerprint,
    )

    model_observations: list[dict[str, object]] = []

    def model(
        stage: BoosterStage,
        current_fields: Mapping[str, object],
        current_references: tuple[SemanticEvidenceReference, ...],
        ledger,
    ) -> DetailSemanticsHypothesisObservation:  # type: ignore[no-untyped-def]
        missing_fields = tuple(
            field for field in requested_fields if field not in current_fields
        )
        if args.disable_llm:
            observation = _blocked_observation(
                stage=stage,
                status="disabled",
                message="Detail Semantics model hypotheses disabled by runtime policy.",
            )
            model_observations.append(observation.to_json())
            return observation
        if _missing_secret(openai_key):
            observation = _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message="Detail Semantics hypotheses require the OpenAI provider key.",
            )
            model_observations.append(observation.to_json())
            return observation
        model_name, reasoning = MODEL_CONFIG[stage]
        max_output = (
            args.luna_max_output_tokens
            if stage == BoosterStage.LUNA_MAX
            else args.model_max_output_tokens
        )
        reserved_cost = _reserved_cost_usd(
            model=model_name,
            reserved_input_tokens=args.reserved_input_tokens,
            max_output_tokens=max_output,
        )
        ceiling = HARD_COST_CEILING_USD[stage]
        if reserved_cost is None:
            observation = _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message=f"No bounded price reservation exists for {model_name}.",
            )
            model_observations.append(observation.to_json())
            return observation
        if reserved_cost > ceiling:
            observation = _blocked_observation(
                stage=stage,
                status="configuration_blocked",
                message=(
                    f"Reserved {model_name} cost ${reserved_cost:.6f} exceeds "
                    f"the stage ceiling ${ceiling:.6f}."
                ),
            )
            model_observations.append(observation.to_json())
            return observation
        observation = request_detail_semantics_hypotheses(
            company_name=args.company_name,
            detail_url=final_url,
            detail_text=detail_text,
            requested_semantic_fields=missing_fields,
            current_semantic_fields=current_fields,
            api_key=openai_key,
            model=model_name,
            reasoning_effort=reasoning,
            max_output_tokens=max_output,
            timeout_seconds=args.model_timeout_seconds,
        )
        model_observations.append(observation.to_json())
        return observation

    def validate(
        observation: DetailSemanticsHypothesisObservation,
    ) -> DetailSemanticsValidationObservation:
        grounded = _references_ground_fields(
            detail_url=final_url,
            detail_text=detail_text,
            semantic_fields=observation.semantic_fields,
            references=observation.evidence_references,
        )
        return DetailSemanticsValidationObservation(
            accepted=grounded,
            classification=(
                "exact_span_grounded_semantic_evidence"
                if grounded
                else "semantic_evidence_grounding_rejected"
            ),
            profile_contract_satisfied=profile_contract_satisfied,
            geography_contract_satisfied=geography_contract_satisfied,
            accepted_semantic_fields=(
                dict(observation.semantic_fields) if grounded else {}
            ),
            accepted_evidence_references=(
                observation.evidence_references if grounded else ()
            ),
            failure_reason=None if grounded else "exact_span_grounding_failed",
            product_authority=False,
        )

    execution = execute_detail_semantics_booster(
        detail_url=final_url,
        decision=gap,
        initial_semantic_fields=deterministic_fields,
        initial_evidence_references=deterministic_references,
        model=model,
        validate=validate,
    )
    if execution.deterministic_resolved:
        outcome = "DETERMINISTIC_SEMANTICS_RESOLVED"
    elif execution.resolved:
        outcome = "SEMANTIC_BOOSTER_RESOLVED"
    elif not gap.semantic_booster_eligible:
        outcome = "SEMANTIC_BOOSTER_NOT_ELIGIBLE"
    else:
        outcome = "RESIDUAL_SEMANTICS_UNRESOLVED"

    return {
        "schema_version": "detail_semantics_booster.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "result": RESULT,
        "outcome": outcome,
        "company_name": args.company_name,
        "detail": {
            "requested_url": args.detail_url,
            "final_url": final_url,
            "status_code": status_code,
            "title": extractor.title,
            "bounded_text_chars": len(detail_text),
            "text_truncated": len(extractor.text) > len(detail_text),
            "raw_html_persisted": False,
        },
        "requested_semantic_fields": list(requested_fields),
        "deterministic_semantic_fields": deterministic_fields,
        "deterministic_evidence_references": [
            item.to_json() for item in deterministic_references
        ],
        "profile_contract_satisfied": profile_contract_satisfied,
        "geography_contract_satisfied": geography_contract_satisfied,
        "detail_supported": detail_supported,
        "gap": gap.to_json(),
        "execution": execution.to_json(),
        "model_observations": model_observations,
        "provider_requests": execution.provider_requests,
        "llm_requests": execution.llm_requests,
        "estimated_model_cost_usd": round(execution.estimated_model_cost_usd, 8),
        "database_writes": 0,
        "gate_writes": 0,
        "lifecycle_writes": 0,
        "ranking_writes": 0,
        "application_writes": 0,
        "product_writes": 0,
        "semantic_authority": False,
        "product_authority": False,
    }


def main() -> int:
    load_local_env_file()
    args = build_parser().parse_args()
    payload = run(args)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
