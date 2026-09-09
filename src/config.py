import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
RUNTIME_ENV_FILE = os.getenv("RUNTIME_ENV_FILE")
ENV_FILE = Path(RUNTIME_ENV_FILE).expanduser() if RUNTIME_ENV_FILE else DEFAULT_ENV_FILE

load_dotenv(dotenv_path=ENV_FILE, override=False)


def get_database_config() -> dict:
    config = {
        "host": os.getenv("POSTGRES_HOST"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }
    application_name = os.getenv("PGAPPNAME")
    if application_name:
        config["application_name"] = application_name
    return config


BA_API_KEY = os.getenv("BA_API_KEY", "jobboerse-jobsuche")
