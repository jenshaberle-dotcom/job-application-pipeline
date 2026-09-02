from pathlib import Path

import scripts.run_product_v1_live_demo as demo


def test_frontend_install_uses_lockfile_ci_when_lockfile_exists(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(demo, "FRONTEND", tmp_path)
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")

    command, mode = demo._frontend_install_command("/usr/bin/npm")

    assert command == ["/usr/bin/npm", "ci"]
    assert mode == "LOCKFILE_CI"


def test_frontend_install_without_lockfile_does_not_create_lockfile(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(demo, "FRONTEND", tmp_path)

    command, mode = demo._frontend_install_command("/usr/bin/npm")

    assert command == [
        "/usr/bin/npm",
        "install",
        "--package-lock=false",
        "--no-audit",
        "--no-fund",
    ]
    assert mode == "LOCKFILE_ABSENT_INSTALL"
