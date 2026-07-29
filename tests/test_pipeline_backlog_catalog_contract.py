from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.validate_ci_contract import ContractError, validate_backlog_catalog


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs" / "planning" / "active" / "backlog_catalog.json"


def _load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _load_capability(relative_path: str) -> dict:
    path = CATALOG_PATH.parent / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


def _write_fixture(tmp_path: Path, catalog: dict, capabilities: dict[str, dict]) -> Path:
    active = tmp_path / "docs" / "planning" / "active"
    (active / "backlog").mkdir(parents=True)
    catalog_path = active / "backlog_catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    for relative_path, payload in capabilities.items():
        path = active / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    return catalog_path


def test_repository_backlog_catalog_contract() -> None:
    assert validate_backlog_catalog() == (10, 67)


def test_canonical_target_profile_contract() -> None:
    profile = _load_catalog()["canonical_target_profile"]

    assert profile["foundation"] == "Machine Learning Engineer"
    assert profile["focus"] == "Data Engineering and data-centric ML systems"
    assert profile["future_direction"] == (
        "AI Reliability / Data & AI Reliability Engineering"
    )
    assert profile["genai_positioning"] == (
        "cross-cutting engineering competency, not a standalone target profile"
    )
    assert (ROOT / profile["active_contract"]).is_file()


def test_backlog_contract_rejects_unknown_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = _load_catalog()
    capabilities = {
        relative: _load_capability(relative)
        for relative in catalog["capability_files"]
    }
    first_file = catalog["capability_files"][0]
    capabilities[first_file]["stories"][0]["dependencies"] = ["UNKNOWN-999"]
    fixture = _write_fixture(tmp_path, catalog, capabilities)
    monkeypatch.setattr("scripts.validate_ci_contract.BACKLOG_ROOT", fixture.parent)

    with pytest.raises(ContractError, match="Unknown dependencies"):
        validate_backlog_catalog(fixture)


def test_backlog_contract_rejects_dependency_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = _load_catalog()
    capabilities = {
        relative: _load_capability(relative)
        for relative in catalog["capability_files"]
    }
    first_file = catalog["capability_files"][0]
    capability_id = capabilities[first_file]["capability"]["id"]
    story_id = capabilities[first_file]["stories"][0]["id"]
    capabilities[first_file]["capability"]["dependencies"] = [story_id]
    capabilities[first_file]["stories"][0]["dependencies"] = [capability_id]
    fixture = _write_fixture(tmp_path, catalog, capabilities)
    monkeypatch.setattr("scripts.validate_ci_contract.BACKLOG_ROOT", fixture.parent)

    with pytest.raises(ContractError, match="dependency cycle"):
        validate_backlog_catalog(fixture)


def test_backlog_contract_rejects_unknown_contradiction_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalog = _load_catalog()
    capabilities = {
        relative: _load_capability(relative)
        for relative in catalog["capability_files"]
    }
    broken = copy.deepcopy(catalog)
    broken["contradictions"][0]["resolution_story"] = "UNKNOWN-999"
    fixture = _write_fixture(tmp_path, broken, capabilities)
    monkeypatch.setattr("scripts.validate_ci_contract.BACKLOG_ROOT", fixture.parent)

    with pytest.raises(ContractError, match="references unknown story"):
        validate_backlog_catalog(fixture)
