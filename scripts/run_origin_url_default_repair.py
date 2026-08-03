"""Stable entry point for the mandatory staged origin repair runtime.

The compatibility path first installs the shared symbol-brand identity contract,
then routes EO-002B, CAND-001, tests, and operator commands through the staged
runtime. Deterministic symbol-brand hosts are validated before Tavily, so a
provider request can no longer be charged for a URL that deterministic evidence
already selected.
"""

from __future__ import annotations

from src.search_intelligence.symbol_brand_identity_bridge import (
    install_symbol_brand_identity_bridge,
)

install_symbol_brand_identity_bridge()

from scripts.run_origin_url_staged_repair import (  # noqa: E402
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
