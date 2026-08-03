"""Compatibility entry point for the mandatory adaptive origin repair runtime.

The product default is implemented in ``run_origin_url_adaptive_repair``. This
module remains the stable import and CLI path used by EO-002B, CAND-001, tests,
and operator commands.
"""

from __future__ import annotations

from scripts.run_origin_url_adaptive_repair import (
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
