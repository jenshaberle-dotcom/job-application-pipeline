"""Query-aware entrypoint for the bounded connector artifact generator."""

from __future__ import annotations

import argparse
from unittest.mock import patch

from scripts import run_employer_origin_connector_artifact_generator as base
from src.search_intelligence.connector_artifact_query_runtime import (
    build_query_aware_implementation,
    validate_query_aware_gate,
)


def run_agent(args: argparse.Namespace) -> int:
    with (
        patch.object(base, "validate_gate", validate_query_aware_gate),
        patch.object(
            base,
            "build_implementation",
            build_query_aware_implementation,
        ),
    ):
        return base.run_agent(args)


def build_parser() -> argparse.ArgumentParser:
    return base.build_parser()


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
