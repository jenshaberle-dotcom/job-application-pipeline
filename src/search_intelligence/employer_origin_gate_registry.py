from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmployerOriginGate:
    gate_order: int
    gate_name: str
    is_hard_gate: bool


OFFICIAL_EMPLOYER_ORIGIN_GATES: tuple[EmployerOriginGate, ...] = (
    EmployerOriginGate(1, "company_candidate", False),
    EmployerOriginGate(2, "source_discovery", True),
    EmployerOriginGate(3, "risk_gate", True),
    EmployerOriginGate(4, "technical_reachability_gate", True),
    EmployerOriginGate(5, "scope_gate", True),
    EmployerOriginGate(6, "defensive_preview_gate", True),
    EmployerOriginGate(7, "relevance_gate", True),
    EmployerOriginGate(8, "detail_evidence_gate", True),
    EmployerOriginGate(9, "incremental_uniqueness_gate", True),
    EmployerOriginGate(10, "connector_candidate_gate", True),
    EmployerOriginGate(11, "connector_validation_gate", True),
    EmployerOriginGate(12, "final_approval_gate", True),
    EmployerOriginGate(13, "controlled_activation_gate", True),
    EmployerOriginGate(14, "bronze_validation", True),
    EmployerOriginGate(15, "silver_validation", True),
    EmployerOriginGate(16, "source_lifecycle_tracking", False),
)

DEFAULT_GATES: tuple[tuple[int, str, bool], ...] = tuple(
    (gate.gate_order, gate.gate_name, gate.is_hard_gate)
    for gate in OFFICIAL_EMPLOYER_ORIGIN_GATES
)

GATE_ORDER_BY_NAME: dict[str, int] = {
    gate.gate_name: gate.gate_order for gate in OFFICIAL_EMPLOYER_ORIGIN_GATES
}

OFFICIAL_GATE_TOTAL = len(OFFICIAL_EMPLOYER_ORIGIN_GATES)


def gate_order(gate_name: str) -> int:
    return GATE_ORDER_BY_NAME[gate_name]
