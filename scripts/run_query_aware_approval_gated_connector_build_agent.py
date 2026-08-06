"""Query-aware entrypoint for the existing S6C approval-gated build contract."""

from __future__ import annotations

import argparse
from unittest.mock import patch

from scripts import run_approval_gated_connector_build_agent as base
from src.search_intelligence.connector_artifact_query_runtime import (
    build_query_aware_implementation,
)


def run_agent(args: argparse.Namespace) -> int:
    with patch.object(
        base,
        "build_implementation",
        build_query_aware_implementation,
    ):
        return base.run_agent(args)


def build_parser() -> argparse.ArgumentParser:
    return base.build_parser()


def main() -> None:
    raise SystemExit(run_agent(build_parser().parse_args()))


if __name__ == "__main__":
    main()
