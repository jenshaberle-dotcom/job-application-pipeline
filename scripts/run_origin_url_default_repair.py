"""Stable entry point for the mandatory staged origin repair runtime.

The compatibility path installs shared normalization, origin-quality,
host-identity, and execution contracts around the staged controller. All callers
therefore receive the same rules for symbol brands, legal suffixes, site-followup
filtering, reusable origin types, third-party rejection, transport isolation,
explicit LLM-disable semantics, and selected entity/locale scope review.
"""

from __future__ import annotations

from src.search_intelligence.origin_search_runtime_contract import (
    install_origin_search_runtime_contract,
)

install_origin_search_runtime_contract()

from src.search_intelligence.origin_host_identity_contract import (  # noqa: E402
    install_origin_host_identity_contract,
)

install_origin_host_identity_contract()

from scripts import run_origin_url_staged_repair as staged  # noqa: E402
from src.search_intelligence.origin_explicit_llm_disable_contract import (  # noqa: E402
    normalize_explicit_llm_disable_outcome,
)
from src.search_intelligence.origin_search_execution_contract import (  # noqa: E402
    install_origin_search_execution_contract,
)
from src.search_intelligence.origin_selection_scope_contract import (  # noqa: E402
    normalize_selection_scope_outcome,
)

install_origin_search_execution_contract()

_STAGED_RUNNER = staged.run_default_repair_for_company


def run_default_repair_for_company(args, company_key):  # type: ignore[no-untyped-def]
    payload = _STAGED_RUNNER(args, company_key)
    payload = normalize_explicit_llm_disable_outcome(
        payload,
        llm_disabled=bool(getattr(args, "disable_llm", False)),
    )
    return normalize_selection_scope_outcome(
        payload,
        target_locale=str(getattr(args, "target_locale", "") or "") or None,
    )


# The staged CLI resolves its module-global runner at execution time. Replacing
# that reference keeps direct CLI, DB audit, EO-002B, and CAND-001 behavior aligned.
staged.run_default_repair_for_company = run_default_repair_for_company

RESULT = staged.RESULT
build_parser = staged.build_parser
main = staged.main
run = staged.run
write_report = staged.write_report

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
