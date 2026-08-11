from pathlib import Path

from src import config


def test_config_env_file_is_bound_to_repository_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    expected_root = Path(config.__file__).resolve().parents[1]

    assert config.PROJECT_ROOT == expected_root
    assert config.ENV_FILE == expected_root / ".env"
