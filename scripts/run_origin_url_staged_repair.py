"""Compatibility entry point for the staged origin repair controller.

The staged contract now delegates to the evidence-backed model-first controller:
deterministic baseline and symbol-brand validation, bounded primary and escalation
model direct-URL hypotheses, residual Tavily search, then deep evidence. Keeping
this module stable preserves existing imports, monkeypatch targets and the public
CLI while changing only the generic stage ordering.
"""

from scripts import run_origin_url_model_first_repair as model_first

# Existing tests and wrappers intentionally patch ``staged.adaptive``. Expose the
# same module object used by the delegated implementation so those patches remain
# authoritative rather than becoming a shadow test path.
adaptive = model_first.adaptive

RESULT = model_first.RESULT
PRIMARY_STAGE = model_first.PRIMARY_STAGE
ESCALATION_STAGE = model_first.ESCALATION_STAGE
build_parser = model_first.build_parser
run_default_repair_for_company = model_first.run_default_repair_for_company
run = model_first.run
main = model_first.main
write_report = model_first.write_report

__all__ = [
    "ESCALATION_STAGE",
    "PRIMARY_STAGE",
    "RESULT",
    "adaptive",
    "build_parser",
    "main",
    "run",
    "run_default_repair_for_company",
    "write_report",
]


if __name__ == "__main__":
    main()
