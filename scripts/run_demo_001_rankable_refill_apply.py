"""Compatibility entrypoint for the retired DEMO-001 refill apply name.

Canonical implementation: scripts.run_product_v1_rankable_refill_apply.
No Product logic lives in this module.
"""
from __future__ import annotations

import sys

from scripts import run_product_v1_rankable_refill_apply as _impl

LEGACY_APPROVAL_TOKEN = "DEMO-001-RANKABLE-REFILL-001"
APPROVAL_TOKEN = LEGACY_APPROVAL_TOKEN
_selected_candidates = _impl._selected_candidates
build_parser = _impl.build_parser


def main() -> int:
    if "--approval-token" in sys.argv:
        index = sys.argv.index("--approval-token") + 1
        if index < len(sys.argv) and sys.argv[index] == LEGACY_APPROVAL_TOKEN:
            sys.argv[index] = _impl.APPROVAL_TOKEN
    return _impl.main()


if __name__ == "__main__":
    raise SystemExit(main())
