"""Public API for bounded multi-model origin adjudication."""

from src.search_intelligence.origin_llm_model_campaign_types import (
    DEFAULT_BENCHMARK_MODELS,
    MODEL_PRICES_USD_PER_MILLION,
    BenchmarkExpectation,
    CaseScore,
    EscalatedAdjudicationRun,
    EscalationSimulation,
    ModelCallObservation,
    canonical_sha256,
)
from src.search_intelligence.origin_llm_model_campaign_provider import (
    Transport,
    adjudicate_model,
    build_request_payload,
)
from src.search_intelligence.origin_llm_model_campaign_evaluation import (
    match_expectation,
    observations_agree,
    parse_expectations,
    recommend_route,
    score_observation,
    should_escalate,
    simulate_escalation,
    summarize_models,
)
from src.search_intelligence.origin_llm_model_campaign_runtime import (
    adjudicate_with_escalation,
)

__all__ = [
    "DEFAULT_BENCHMARK_MODELS",
    "MODEL_PRICES_USD_PER_MILLION",
    "BenchmarkExpectation",
    "CaseScore",
    "EscalatedAdjudicationRun",
    "EscalationSimulation",
    "ModelCallObservation",
    "Transport",
    "adjudicate_model",
    "adjudicate_with_escalation",
    "build_request_payload",
    "canonical_sha256",
    "match_expectation",
    "observations_agree",
    "parse_expectations",
    "recommend_route",
    "score_observation",
    "should_escalate",
    "simulate_escalation",
    "summarize_models",
]
