from __future__ import annotations

import argparse
import json

from src.search_intelligence.product_v1_contenders import (
    DEFAULT_CONTENDER_LIMIT,
    ProductV1ContenderRepository,
    build_contender_manifest,
)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Build a DB-enforced read-only Product V1 contender inspection pool. "
            "This is preselection, not ranking or vacancy-activity validation."
        )
    )
    parser.add_argument(
        "--limit",
        type=positive_int,
        default=DEFAULT_CONTENDER_LIMIT,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repository = ProductV1ContenderRepository()
    read_only, rows = repository.load_inventory_read_only()
    manifest = build_contender_manifest(
        rows,
        transaction_read_only=read_only,
        limit=args.limit,
    )
    print(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
