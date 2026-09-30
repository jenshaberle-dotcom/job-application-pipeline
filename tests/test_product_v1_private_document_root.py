from __future__ import annotations

import os
from pathlib import Path

from scripts import run_jap_control_center_runtime as runtime
from scripts.run_product_v1_operator_control_center import configure_private_document_root


def test_private_document_root_defaults_and_exports_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", raising=False)

    root = configure_private_document_root()

    assert root == (tmp_path / "private_application_sources").resolve()
    assert root.is_dir()
    assert os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] == str(root)


def test_private_document_root_respects_operator_override(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "custom-private"
    monkeypatch.setenv("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", str(root))

    configured = configure_private_document_root()

    assert configured == root.resolve()
    assert configured.is_dir()
    assert os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] == str(root.resolve())


def test_runtime_launcher_defaults_private_root_to_repo(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(live_demo, "ROOT", tmp_path)
    monkeypatch.delenv("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", raising=False)

    root = runtime._configure_launcher_private_document_root()

    expected = (tmp_path / "private_application_sources").resolve()
    assert root == expected
    assert root.is_dir()
    assert os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] == str(expected)


def test_runtime_launcher_preserves_private_root_override(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(live_demo, "ROOT", tmp_path / "ignored-repo-root")
    override = tmp_path / "operator-private"
    monkeypatch.setenv("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", str(override))

    root = runtime._configure_launcher_private_document_root()

    assert root == override.resolve()
    assert root.is_dir()
    assert os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] == str(
        override.resolve()
    )
