from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.search_intelligence.architecture_contracts import (
    AGENT_PERMISSIONS,
    CANDIDATE_LIFECYCLE_STATES,
    GATE_CONTRACT_REQUIRED_FIELDS,
    MATURITY_TARGETS_90_PLUS,
    SAFETY_ZONES,
    SECURITY_BASELINE_CONTROLS,
    validate_architecture_contracts,
)


def main() -> int:
    violations = validate_architecture_contracts()
    print("ARCH-001 architecture contract check")
    print(f"safety_zones={len(SAFETY_ZONES)}")
    print(f"agent_permissions={len(AGENT_PERMISSIONS)}")
    print(f"candidate_lifecycle_states={len(CANDIDATE_LIFECYCLE_STATES)}")
    print(f"gate_required_fields={len(GATE_CONTRACT_REQUIRED_FIELDS)}")
    print(f"security_controls={len(SECURITY_BASELINE_CONTROLS)}")
    print(f"maturity_targets={len(MATURITY_TARGETS_90_PLUS)}")
    required_docs = [
        Path("docs/reference/security/safety_security_state_architecture.md"),
        Path("docs/reference/agents/agent_permission_matrix.md"),
        Path("docs/current/pipeline.md"),
        Path("docs/reference/scoring-and-gates/gate_contract_baseline.md"),
        Path("docs/reference/security/search_intelligence_security_baseline.md"),
        Path("docs/archive/planning/architecture_freeze_maturity_campaign.md"),
        Path("docs/decisions/adr/033_define_search_intelligence_safety_security_boundaries.md"),
    ]
    missing_docs = [str(path) for path in required_docs if not path.exists()]
    if missing_docs:
        violations.append("Missing architecture docs: " + ", ".join(missing_docs))
    if violations:
        print("violations:")
        for violation in violations:
            print(f"- {violation}")
        return 1
    print("status=pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
