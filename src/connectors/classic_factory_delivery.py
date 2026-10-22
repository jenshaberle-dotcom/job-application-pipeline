"""Durable receipts for the Classic factory; no scheduler or runner authority."""
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Callable


class ReconciliationRequired(RuntimeError):
    pass


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    # WSL/Linux host: make the rename durable as well as the file contents.
    if os.name == "posix":
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class DeliveryJournal:
    """Caller must hold the database advisory lock for the entire operation."""

    def __init__(self, path: Path, binding: dict) -> None:
        self.path = path
        self.stage_dir = path.with_suffix(".stages")
        from .workload_progress import WorkloadProgress
        self.progress = WorkloadProgress(path.parent / "native-progress.json")
        self.data = {"schema": "jap.classic_factory_delivery.v1", "binding": binding, "stages": {}}
        if path.exists():
            saved = json.loads(path.read_text())
            if saved["binding"] != binding:
                raise ValueError("receipt_binding_changed")
            for receipt in sorted(self.stage_dir.glob("*.json")):
                entry = json.loads(receipt.read_text())
                self.data["stages"][entry["key"]] = entry["stage"]

    def save(self, key: str | None = None) -> None:
        if not self.path.exists():
            atomic_json(self.path, {k: v for k, v in self.data.items() if k != "stages"})
        # One bounded receipt per candidate/phase; no quadratic population rewrites.
        keys = [key] if key is not None else self.data["stages"]
        for name in keys:
            atomic_json(self.stage_dir / (fingerprint(name) + ".json"), {
                "key": name, "stage": self.data["stages"][name],
            })

    def stage(self, key: str, operation: Callable[[], dict], *, effect: bool) -> dict:
        previous = self.data["stages"].get(key, {})
        if previous.get("state") == "SUCCEEDED":
            return previous["result"]
        if previous.get("state") in {"RUNNING", "HELD"} and previous.get("effect"):
            raise ReconciliationRequired(key)
        self.data["stages"][key] = {
            "state": "RUNNING", "effect": effect,
            "started_at": datetime.now(UTC).isoformat(),
        }
        self.save(key)  # intent must be durable before the first possible effect
        worker = self.progress.begin(key)
        try:
            result = operation()
        except BaseException as exc:
            self.data["stages"][key].update(
                state="HELD" if effect else "FAILED", error_type=type(exc).__name__,
            )
            try:
                self.save(key)
            finally:
                self.progress.end(key, worker, failed=True)
            raise
        self.data["stages"][key].update(
            state="SUCCEEDED", result=result, completed_at=datetime.now(UTC).isoformat(),
        )
        try:
            self.save(key)
        except BaseException:
            self.progress.end(key, worker, failed=True)
            raise
        self.progress.end(key, worker)
        return result


def delivery_summary(stages: dict, population_count: int) -> dict:
    deliveries = [v["result"] for k, v in stages.items()
                  if k.startswith("ingest:") and v.get("state") == "SUCCEEDED"]
    loaded = sum(v["observed_jobs"] for v in deliveries)
    inserted = sum(v["inserted_jobs"] for v in deliveries)
    held = sorted(k for k, v in stages.items() if v.get("state") in {"RUNNING", "HELD"})
    return {
        "population_count": population_count,
        "sources_ingested": len(deliveries),
        "observed_jobs": loaded, "inserted_jobs": inserted,
        "bronze_delivery_proven": loaded > 0,
        "held_stages": held,
        "profile_relevance_proven": False,
        "ranking_fitting_proven": False,
        "e2e_accepted": False,
    }
