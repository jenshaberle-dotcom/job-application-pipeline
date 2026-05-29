from __future__ import annotations

# Compatibility wrapper: the S4A implementation lives in
# scripts.run_employer_origin_connector_artifact_generator.
# Keep the old import/CLI path stable for existing docs, tests and local habits.

from scripts.run_employer_origin_connector_artifact_generator import *  # noqa: F401,F403
from scripts.run_employer_origin_connector_artifact_generator import main


if __name__ == "__main__":
    main()
