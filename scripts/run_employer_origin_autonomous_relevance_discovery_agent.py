"""Run autonomous relevance discovery for an employer-origin candidate.

This is a product-facing alias for the bounded relevance-evidence probe. The
agent does not consume human-provided job URLs as normal product input. It scans
a bounded set of same-/related-host job/search pages, persists discovered
job-detail evidence and learns classification signals only from accepted
autonomous evidence.
"""

from __future__ import annotations

from scripts.run_employer_origin_relevance_evidence_probe_agent import build_parser, run


def main() -> None:
    raise SystemExit(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
