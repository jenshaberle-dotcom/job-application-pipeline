from __future__ import annotations

from scripts import run_deterministic_connector_builder_layer_audit as base_audit
from scripts.run_origin_source_discovery_agent_v4 import run_for_company as run_origin_discovery_v4


def main() -> int:
    # A/B harness only: preserve every connector-builder layer and authority rule,
    # swapping only the provider-free origin discovery planner.
    base_audit.run_origin_discovery = run_origin_discovery_v4
    return base_audit.main()


if __name__ == "__main__":
    raise SystemExit(main())
