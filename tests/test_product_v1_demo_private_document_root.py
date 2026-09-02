from __future__ import annotations

import os
from pathlib import Path

from scripts.run_product_v1_demo_control_center import configure_demo_private_document_root


def test_demo_private_document_root_defaults_and_exports_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", raising=False)

    root = configure_demo_private_document_root()

    assert root == (tmp_path / "private_application_sources").resolve()
    assert root.is_dir()
    assert os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] == str(root)


def test_demo_private_document_root_respects_operator_override(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "custom-private"
    monkeypatch.setenv("PRODUCT_V1_PRIVATE_DOCUMENT_ROOT", str(root))

    configured = configure_demo_private_document_root()

    assert configured == root.resolve()
    assert configured.is_dir()
    assert os.environ["PRODUCT_V1_PRIVATE_DOCUMENT_ROOT"] == str(root.resolve())
