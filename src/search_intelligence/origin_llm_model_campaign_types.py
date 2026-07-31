"""Shared contracts for the bounded origin LLM model campaign."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Mapping

from src.search_intelligence.origin_llm_adjudication import LLMAdjudicationResult

MODEL_PRICES_USD_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.6-terra": (2.50, 15.00),
    "gpt-5.5": (5.00, 30.00),
}
DEFAULT_BENCHMARK_MODELS = (
    "gpt-5.4-mini",
    "gpt-5.6-terra",
    "gpt-5.5",
)


@dataclass(frozen=True)
class BenchmarkExpectation:
    case_id: str
    company_name_contains: str
    expected_manual_review: bool
    acceptable_url_contains: tuple[str, ...] = ()
    acceptable_source_grades: tuple[str, ...] = ()
    expected_locale: str | None = None
    weight: float = 1.0
    notes: str = ""


@dataclass(frozen=True)
class ModelCallObservation:
    company_key: str
    company_name: str
    model_requested: str
    model_returned: str | None
    packet_sha256: str
    request_contract_sha256: str
    latency_ms: int
    estimated_cost_usd: float
    result: LLMAdjudicationResult

    def to_json(self) -> dict[str, object]:
        return {
            "company_key": self.company_key,
            "company_name": self.company_name,
            "model_requested": self.model_requested,
            "model_returned": self.model_returned,
            "packet_sha256": self.packet_sha256,
            "request_contract_sha256": self.request_contract_sha256,
            "latency_ms": self.latency_ms,
            "estimated_cost_usd": round(self.estimated_cost_usd, 8),
            "provider_result": self.result.to_json(),
        }


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    company_key: str
    model: str
    weight: float
    score: float
    critical_failure: bool
    effective_candidate_id: str | None
    effective_candidate_url: str | None
    reasons: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        payload = asdict(self)
        payload["reasons"] = list(self.reasons)
        return payload


@dataclass(frozen=True)
class EscalatedAdjudicationRun:
    company_key: str
    company_name: str
    primary: ModelCallObservation
    escalation: ModelCallObservation | None
    trigger_reason: str | None
    outcome: str

    def to_json(self) -> dict[str, object]:
        return {
            "company_key": self.company_key,
            "company_name": self.company_name,
            "primary": self.primary.to_json(),
            "escalation": None if self.escalation is None else self.escalation.to_json(),
            "trigger_reason": self.trigger_reason,
            "outcome": self.outcome,
            "review_output_only_not_pipeline_input": True,
        }


@dataclass(frozen=True)
class EscalationSimulation:
    company_key: str
    trigger_reason: str | None
    primary_model: str
    escalation_model: str
    primary_score: float
    escalation_score: float
    score_lift: float
    corrected: bool
    outcome: str

    def to_json(self) -> dict[str, object]:
        return asdict(self)


def canonical_sha256(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
