from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    module = import_module("scripts.run_market_opportunity_vacancy_bridge")
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
