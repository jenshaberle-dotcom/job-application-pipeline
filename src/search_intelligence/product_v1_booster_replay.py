"""Product V1 input adapters for the canonical LLM-BOOST-001 replay guard.

These adapters turn already-authoritative deterministic Product V1 state into
stable provider-preflight identities. They do not decide product truth, run a
provider, read or write a cache, or mutate database/product state.

The unresolved assessment/ranking/drafting scope remains caller authority. This
avoids duplicating stage-specific resolution semantics here: the caller supplies
the exact scope it is about to send to the canonical booster cascade, and this
module binds that scope to a stable source/input identity.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping

from src.search_intelligence.llm_booster_policy import (
    BoosterReplayDecision,
    BoosterSurface,
    build_booster_replay_decision,
)
from src.search_intelligence.product_v1_application_context import (
    ProductV1ApplicationContext,
)
from src.search_intelligence.product_v1_assessment_evidence import (
    ProductV1AssessmentEvidence,
)
from src.search_intelligence.product_v1_ranking_evidence import (
    ProductV1RankingEvidence,
)


def _canonical_hash(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ProductV1BoosterInput:
    surface: BoosterSurface
    source_identity: str
    normalized_input_hash: str
    provider_requests: int = 0
    llm_requests: int = 0
    database_requests: int = 0
    product_writes: int = 0
    product_authority: bool = False

    def __post_init__(self) -> None:
        if self.surface not in {
            BoosterSurface.PRODUCT_V1_ASSESSMENT,
            BoosterSurface.PRODUCT_V1_RANKING,
            BoosterSurface.PRODUCT_V1_APPLICATION,
        }:
            raise ValueError("Product V1 booster input requires a Product V1 surface")
        if not self.source_identity.strip() or not self.normalized_input_hash.strip():
            raise ValueError("Product V1 booster input identity fields must be non-empty")

    def replay_decision(
        self,
        *,
        unresolved_scope: Iterable[str],
        prior_terminal_input_fingerprints: Iterable[str] = (),
    ) -> BoosterReplayDecision:
        return build_booster_replay_decision(
            surface=self.surface,
            source_identity=self.source_identity,
            normalized_input_hash=self.normalized_input_hash,
            unresolved_scope=unresolved_scope,
            prior_terminal_input_fingerprints=prior_terminal_input_fingerprints,
        )


def assessment_booster_input(
    evidence: ProductV1AssessmentEvidence,
) -> ProductV1BoosterInput:
    source_identity = str(evidence.source_url or "").strip()
    if not source_identity:
        raise ValueError("assessment booster replay requires source_url identity")
    return ProductV1BoosterInput(
        surface=BoosterSurface.PRODUCT_V1_ASSESSMENT,
        source_identity=source_identity,
        normalized_input_hash=_canonical_hash(evidence.canonical_payload()),
    )


def ranking_booster_input(
    evidence: ProductV1RankingEvidence,
    *,
    source_identity: str,
) -> ProductV1BoosterInput:
    source = source_identity.strip()
    if not source:
        raise ValueError("ranking booster replay requires explicit source identity")
    return ProductV1BoosterInput(
        surface=BoosterSurface.PRODUCT_V1_RANKING,
        source_identity=source,
        normalized_input_hash=_canonical_hash(evidence.canonical_payload()),
    )


def application_booster_input(
    context: ProductV1ApplicationContext,
) -> ProductV1BoosterInput:
    source_url = str(context.target.source_url or "").strip()
    if not source_url:
        raise ValueError("application booster replay requires target source_url")
    source_identity = f"silver_job:{context.target.silver_job_id}|{source_url}"
    return ProductV1BoosterInput(
        surface=BoosterSurface.PRODUCT_V1_APPLICATION,
        source_identity=source_identity,
        normalized_input_hash=_canonical_hash(context.source_manifest()),
    )


__all__ = [
    "ProductV1BoosterInput",
    "application_booster_input",
    "assessment_booster_input",
    "ranking_booster_input",
]
