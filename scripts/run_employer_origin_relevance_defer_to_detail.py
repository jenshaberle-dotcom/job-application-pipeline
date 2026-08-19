from __future__ import annotations

import argparse

import psycopg

from scripts.run_employer_origin_gate_agent import GateOutcome
from scripts.run_employer_origin_preconnector_precondition_agent import Repository
from scripts.run_origin_source_discovery_agent import load_local_env_file
from src.config import get_database_config
from src.search_intelligence.preconnector_relevance_deferral import (
    evaluate_relevance_deferral,
)

BOUNDARY = (
    "existing_candidate_only",
    "all_safety_predecessors_must_already_pass",
    "deterministic_relevance_repair_only",
    "target_location_or_remote_proof_still_required_at_detail_evidence",
    "no_provider_or_llm",
    "no_connector_build_or_registration",
    "no_source_activation",
    "no_ingestion_or_product_mutation",
)


def run_agent(args: argparse.Namespace) -> int:
    load_local_env_file()
    with psycopg.connect(**get_database_config()) as conn:
        repo = Repository(conn)
        candidate = repo.load_candidate(candidate_id=args.candidate_id, company_key=args.company_key)
        gates = repo.load_gates(candidate.id)
        decision = evaluate_relevance_deferral(gates)

        print(f"candidate_id: {candidate.id}")
        print(f"candidate: {candidate.company_key} | {candidate.source_name_candidate}")
        print("boundary: " + ", ".join(BOUNDARY))
        print(f"relevance_deferral: eligible={decision.eligible} reason={decision.reason_code}")

        if not decision.eligible:
            print("STOP: deterministic relevance deferral is not eligible from current gate truth.")
            return 2

        outcome = GateOutcome(
            gate_name="relevance_gate",
            gate_status="passed",
            decision="passed",
            stop_reason=None,
            evidence={
                **decision.evidence,
                "agent": "preconnector_relevance_defer_to_detail",
                "source_relevance_gate_stop_reason": gates["relevance_gate"].get("stop_reason"),
            },
        )
        if not args.dry_run:
            repo.record_gate(candidate.id, outcome, args.reviewed_by)
            conn.commit()
        print(
            "NEXT: relevance is sufficient for listing-level progression; "
            "detail_evidence_gate must still prove concrete profile + target/remote evidence."
        )
        if args.dry_run:
            print("DRY RUN: no DB gate state was changed.")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically defer landing-page target relevance to concrete detail evidence "
            "without weakening risk or final detail requirements."
        )
    )
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-id", type=int)
    candidate.add_argument("--company-key")
    parser.add_argument("--reviewed-by", default="preconnector_relevance_defer_to_detail")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
