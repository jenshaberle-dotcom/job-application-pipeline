"""Compatibility entrypoint for the retired DEMO-001 refill scout name.

Canonical implementation: scripts.run_product_v1_rankable_refill_scout.
No Product logic lives in this module.
"""
from scripts import run_product_v1_rankable_refill_scout as _impl

_authoritative_geography = _impl._authoritative_geography
_load_candidate_facts = _impl._load_candidate_facts
_load_rows = _impl._load_rows
scout = _impl.scout
build_parser = _impl.build_parser


def main() -> int:
    return _impl.main()


if __name__ == "__main__":
    raise SystemExit(main())
