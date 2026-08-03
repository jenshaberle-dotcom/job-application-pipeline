"""Compatibility entry point for the mandatory adaptive origin repair runtime.

The product default is implemented in ``run_origin_url_adaptive_repair``. This
module remains the stable import and CLI path used by EO-002B, CAND-001, tests,
and operator commands.

Before importing the adaptive runtime, the stable entry point installs the
generic symbol-brand identity bridge. This keeps URL generation and identity
scoring on the same normalization contract: a candidate such as
``career.1and1.org`` cannot be generated from ``1&1`` and then rejected merely
because the legacy scorer discarded its digits and symbol.
"""

from __future__ import annotations

from src.search_intelligence.symbol_brand_identity_bridge import (
    install_symbol_brand_identity_bridge,
)

install_symbol_brand_identity_bridge()

from scripts.run_origin_url_adaptive_repair import (  # noqa: E402
    RESULT,
    build_parser,
    main,
    run,
    run_default_repair_for_company,
    write_report,
)

__all__ = [
    "RESULT",
    "build_parser",
    "main",
    "run",
    "run_default_repair_for_company",
    "write_report",
]


if __name__ == "__main__":
    main()
