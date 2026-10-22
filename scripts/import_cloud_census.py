"""Plan or atomically import a verified full Cloud Census. Default: read-only plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import psycopg

from src.config import get_database_config
from src.search_intelligence.cloud_census_import import apply_import, plan_import


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    export = json.loads(args.input.read_text(encoding="utf-8"))
    with psycopg.connect(**get_database_config(), autocommit=True) as conn:
        if args.apply:
            result = apply_import(conn, export)
        else:
            conn.execute("SET default_transaction_read_only=on")
            existing = [dict(zip(("id", "company_key", "company_name"), row)) for row in
                        conn.execute("SELECT id,company_key,company_name FROM employer_origin_source_candidates")]
            result = plan_import(export, existing)
            result.pop("candidates")
            result["status"] = "PLAN_ONLY"
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
