from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from scripts.run_product_e2e_origin_url_bridge import cand001_args
from src.search_intelligence.product_e2e_origin_url_bridge import OriginUrlBridgePlan


def test_bridge_forwards_exact_candidate_id_map_to_cand001(tmp_path: Path) -> None:
    plan = OriginUrlBridgePlan(
        candidate_id=46,
        company_key="1_1",
        company_name="1&1",
        discovery_source_class="aggregator_company_discovery",
        candidate_status="discovery",
        current_candidate_url=None,
        action="run_bounded_origin_discovery_then_cand001",
        plan_status="ready_for_origin_discovery",
        origin_discovery_allowed=True,
        apply_target_allowed=True,
        reason="test",
    )
    args = Namespace(
        target_location="Hannover",
        target_locale="de",
        reviewed_by="jens",
        apply=True,
        timeout_seconds=8.0,
        max_url_candidates=12,
        market_evidence_limit=30,
        max_evidence_candidates=4,
        max_evidence_http_requests=12,
        max_response_bytes=750_000,
    )

    forwarded = cand001_args(
        args,
        selected=(plan,),
        run_dir=tmp_path,
    )

    assert forwarded.company_key == ["1_1"]
    assert forwarded.candidate_id_by_company_key == {"1_1": 46}
    assert forwarded.disable_tavily is True
    assert forwarded.disable_llm is True
    assert forwarded.search_provider == ["none"]


def test_bridge_runner_advertises_exact_identity_boundary() -> None:
    script = Path("scripts/run_product_e2e_origin_url_bridge.py").read_text(
        encoding="utf-8"
    )
    assert '"exact_candidate_identity_forwarded_to_cand001": True' in script
