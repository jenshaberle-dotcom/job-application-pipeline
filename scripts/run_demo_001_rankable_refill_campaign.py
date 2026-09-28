"""Compatibility entrypoint for the retired DEMO-001 refill campaign name.

Canonical implementation: scripts.run_product_v1_rankable_refill_campaign.
No Product logic lives in this module.
"""
from __future__ import annotations

import sys

from scripts import run_product_v1_rankable_refill_campaign as _impl

LEGACY_APPROVAL_TOKEN = "DEMO-001-RANKABLE-REFILL-CAMPAIGN-001"
APPROVAL_TOKEN = LEGACY_APPROVAL_TOKEN
MATERIALIZATION_APPROVAL_TOKEN = _impl.MATERIALIZATION_APPROVAL_TOKEN
MATERIALIZATION_OUTPUT = _impl.MATERIALIZATION_OUTPUT
subprocess = _impl.subprocess
_selected = _impl._selected
_materialize_missing = _impl._materialize_missing
_refresh_selected = _impl._refresh_selected
build_parser = _impl.build_parser


def main() -> int:
    if "--approval-token" in sys.argv:
        index = sys.argv.index("--approval-token") + 1
        if index < len(sys.argv) and sys.argv[index] == LEGACY_APPROVAL_TOKEN:
            sys.argv[index] = _impl.APPROVAL_TOKEN
    return _impl.main()


if __name__ == "__main__":
    raise SystemExit(main())
