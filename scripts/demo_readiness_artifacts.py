"""Small fail-safe helpers for DEMO-001 readiness diagnostics."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import object as _object  # type: ignore[attr-defined]


def atomic_write_json(path: Path, payload: object) -> None:
    """Publish one complete JSON diagnostic atomically within its target directory."""
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


__all__ = ["atomic_write_json"]
