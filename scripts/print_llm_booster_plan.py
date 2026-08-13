"""Print the side-effect-free LLM-BOOST-001 policy plan."""

from __future__ import annotations

import argparse
import json

from src.search_intelligence.llm_booster_policy import (
    BoosterSurface,
    TavilyState,
    build_booster_plan,
    origin_empirical_expected_model_cost_usd,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", choices=[item.value for item in BoosterSurface], required=True)
    parser.add_argument(
        "--tavily-state",
        choices=[item.value for item in TavilyState],
        default=TavilyState.AVAILABLE.value,
    )
    parser.add_argument("--deterministic-resolved", action="store_true")
    parser.add_argument("--external-information-gap", action="store_true")
    parser.add_argument("--recurring-unchanged-fingerprint", action="store_true")
    return parser


def run(args: argparse.Namespace) -> int:
    plan = build_booster_plan(
        surface=BoosterSurface(args.surface),
        tavily_state=TavilyState(args.tavily_state),
        deterministic_resolved=args.deterministic_resolved,
        external_information_gap=args.external_information_gap,
        recurring_unchanged_fingerprint=args.recurring_unchanged_fingerprint,
    )
    payload = plan.to_json()
    payload["origin_empirical_expected_model_cost_after_deterministic_miss_usd"] = round(
        origin_empirical_expected_model_cost_usd(), 8
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
