"""Retain actually received public bytes for the parent Bronze writer."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4


def retain(url, payload):
    directory = os.environ.get("JAP_CENSUS_EVIDENCE_DIR")
    if not directory:
        return
    root = Path(directory)
    # Per-source storage ceiling; never silently discard a received response.
    if sum(p.stat().st_size for p in root.glob("*.body")) + len(payload) > 128_000_000:
        raise RuntimeError("SOURCE_EVIDENCE_BUDGET_EXCEEDED")
    identity = uuid4().hex
    with (root / (identity + ".body")).open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    with (root / (identity + ".json")).open("x", encoding="utf-8") as stream:
        json.dump({"url": url, "sha256": hashlib.sha256(payload).hexdigest()}, stream)
        stream.flush()
        os.fsync(stream.fileno())
