"""Model summaries and cost-aware route recommendation."""

from __future__ import annotations

from typing import Mapping, Sequence

from src.search_intelligence.origin_llm_model_campaign_types import (
    CaseScore,
    EscalationSimulation,
    ModelCallObservation,
)


def summarize_models(
    observations: Sequence[ModelCallObservation],
    scores: Sequence[CaseScore],
    *,
    model_order: Sequence[str],
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for model in model_order:
        model_observations = [item for item in observations if item.model_requested == model]
        model_scores = [item for item in scores if item.model == model]
        completed = sum(item.result.status == "completed" for item in model_observations)
        total_cost = sum(item.estimated_cost_usd for item in model_observations)
        total_weight = sum(item.weight for item in model_scores)
        mean_score = (
            sum(item.score * item.weight for item in model_scores) / total_weight
            if total_weight
            else 0.0
        )
        mean_latency = (
            sum(item.latency_ms for item in model_observations) / len(model_observations)
            if model_observations
            else 0.0
        )
        summaries.append(
            {
                "model": model,
                "case_count": len(model_observations),
                "completed_count": completed,
                "completed_rate": round(
                    completed / len(model_observations), 4
                )
                if model_observations
                else 0.0,
                "mean_quality_score": round(mean_score, 4),
                "critical_failure_count": sum(
                    item.critical_failure for item in model_scores
                ),
                "estimated_cost_usd": round(total_cost, 8),
                "mean_latency_ms": round(mean_latency, 1),
            }
        )
    return summaries


def recommend_route(
    summaries: Sequence[Mapping[str, object]],
    simulations_by_pair: Mapping[str, Sequence[EscalationSimulation]],
) -> dict[str, object]:
    if not summaries:
        return {
            "primary_model": None,
            "escalation_model": None,
            "escalation_value_proven": False,
            "reason": "no_model_results",
        }
    by_model = {str(item["model"]): item for item in summaries}
    best_score = max(float(item["mean_quality_score"]) for item in summaries)

    route_candidates: list[dict[str, object]] = []
    for primary_model, primary in by_model.items():
        primary_score = float(primary["mean_quality_score"])
        primary_cost = float(primary["estimated_cost_usd"])
        critical_count = int(primary["critical_failure_count"])

        if (
            critical_count == 0
            and primary_score >= 0.80
            and primary_score >= best_score - 0.05
        ):
            route_candidates.append(
                {
                    "primary_model": primary_model,
                    "escalation_model": None,
                    "route_score": primary_score,
                    "route_cost": primary_cost,
                    "corrected_case_count": 0,
                    "mean_lift": 0.0,
                    "value_proven": False,
                }
            )

        for pair_key, simulations in simulations_by_pair.items():
            pair_primary, pair_escalation = pair_key.split("->", 1)
            if pair_primary != primary_model or pair_escalation not in by_model:
                continue
            triggered = [item for item in simulations if item.trigger_reason is not None]
            if not triggered:
                continue
            corrected_count = sum(item.corrected for item in triggered)
            unresolved_critical = max(0, critical_count - corrected_count)
            route_scores = [
                item.escalation_score if item.trigger_reason is not None else item.primary_score
                for item in simulations
            ]
            route_score = sum(route_scores) / len(route_scores) if route_scores else 0.0
            mean_lift = sum(item.score_lift for item in triggered) / len(triggered)
            escalation_summary = by_model[pair_escalation]
            escalation_case_cost = (
                float(escalation_summary["estimated_cost_usd"])
                / max(1, int(escalation_summary["case_count"]))
            )
            route_cost = primary_cost + escalation_case_cost * len(triggered)
            value_proven = corrected_count >= 1 and mean_lift >= 0.10
            if (
                unresolved_critical == 0
                and route_score >= 0.80
                and route_score >= best_score - 0.05
                and value_proven
            ):
                route_candidates.append(
                    {
                        "primary_model": primary_model,
                        "escalation_model": pair_escalation,
                        "route_score": route_score,
                        "route_cost": route_cost,
                        "corrected_case_count": corrected_count,
                        "mean_lift": mean_lift,
                        "value_proven": True,
                    }
                )

    if not route_candidates:
        fallback = min(
            summaries,
            key=lambda item: (
                -float(item["mean_quality_score"]),
                int(item["critical_failure_count"]),
                float(item["estimated_cost_usd"]),
            ),
        )
        return {
            "primary_model": str(fallback["model"]),
            "escalation_model": None,
            "escalation_value_proven": False,
            "reason": "no_safe_cost_efficient_route_proven",
        }

    chosen = min(
        route_candidates,
        key=lambda item: (
            float(item["route_cost"]),
            -float(item["route_score"]),
            str(item["primary_model"]),
        ),
    )
    return {
        "primary_model": chosen["primary_model"],
        "escalation_model": chosen["escalation_model"],
        "escalation_value_proven": bool(chosen["value_proven"]),
        "corrected_case_count": int(chosen["corrected_case_count"]),
        "mean_triggered_score_lift": round(float(chosen["mean_lift"]), 4),
        "estimated_route_cost_usd": round(float(chosen["route_cost"]), 8),
        "route_quality_score": round(float(chosen["route_score"]), 4),
        "reason": (
            "observed_quality_lift_on_primary_failures"
            if chosen["value_proven"]
            else "cheapest_model_within_quality_tolerance"
        ),
    }
