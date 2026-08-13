"""Stable entry point for the mandatory origin repair runtime.

The compatibility path installs shared normalization, origin-quality,
host-identity, reviewed-alias, live-evidence, operator-precedence, and execution
contracts around the empirically validated controller. All callers therefore
receive the same deterministic -> Luna -> Terra -> Sol -> Luna(max) -> residual
Tavily rules plus the existing selected-entity/locale safeguards.
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

# Reviewed aliases are deliberately the outer identity wrapper. The generic host
# gate runs first; registered evidence may then explain a weak identity without a
# later generic wrapper silently undoing that explicit decision.
from src.search_intelligence.origin_registered_identity_contract import (  # noqa: E402
    install_origin_registered_identity_contract,
)

install_origin_registered_identity_contract()

from src.search_intelligence.origin_registered_short_alias_live_evidence_contract import (  # noqa: E402
    install_origin_registered_short_alias_live_evidence_contract,
)

install_origin_registered_short_alias_live_evidence_contract()

from scripts import run_origin_url_empirical_cascade as staged  # noqa: E402
from src.search_intelligence.origin_explicit_llm_disable_contract import (  # noqa: E402
    normalize_explicit_llm_disable_outcome,
)
from src.search_intelligence.origin_explicit_tavily_disable_contract import (  # noqa: E402
    normalize_explicit_tavily_disable_outcome,
)
from src.search_intelligence.origin_operator_url_precedence_contract import (  # noqa: E402
    run_with_operator_url_precedence,
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
    payload = run_with_operator_url_precedence(
        _STAGED_RUNNER,
        staged_module=staged,
        args=args,
        company_key=company_key,
    )
    payload = normalize_explicit_tavily_disable_outcome(
        payload,
        tavily_disabled=bool(getattr(args, "disable_tavily", False)),
    )
    payload = normalize_explicit_llm_disable_outcome(
        payload,
        llm_disabled=bool(getattr(args, "disable_llm", False)),
    )
    return normalize_selection_scope_outcome(
        payload,
        target_locale=str(getattr(args, "target_locale", "") or "") or None,
    )


# The canonical CLI resolves its module-global runner at execution time. Replacing
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
