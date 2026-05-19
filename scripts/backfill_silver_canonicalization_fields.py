"""Backfill canonicalization fields for existing Silver jobs.

Run from the project root with:

    python -m scripts.backfill_silver_canonicalization_fields
"""

from src.silver.repository import SilverJobRepository


def main() -> None:
    repository = SilverJobRepository()
    updated_count = repository.backfill_canonicalization_fields()

    print(f"Backfilled silver canonicalization fields: {updated_count}")


if __name__ == "__main__":
    main()
