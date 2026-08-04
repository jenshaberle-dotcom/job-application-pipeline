"""Stable entry point for the mandatory staged origin repair runtime.

The compatibility path installs one shared search/runtime contract before the
staged controller is imported. This keeps brand generation, identity scoring,
legal-suffix cleanup, origin-quality gates, and site-follow-up filtering
consistent for EO-002B, CAND-001, database audits, tests, and operator commands.
After import, the execution contract isolates transport failures and prevents
raw unrelated search domains from creating site-follow-up queries.
"""

from __future__ import annotations

from src.search_intelligence.origin_search_runtime_contract import (
    install_origin_search_runtime_contract,
)

install_origin_search_runtime_contract()

from scripts.run_origin_url_staged_repair import (  # noqa: E402
    RESULT,
    build_parser,
    main,
    run,
    run_default_repair_for_company,
    write_report,
)
from src.search_intelligence.origin_search_execution_contract import (  # noqa: E402
    install_origin_search_execution_contract,
)

install_origin_search_execution_contract()

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
