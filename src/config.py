import os
from dotenv import load_dotenv

load_dotenv()


def get_database_config() -> dict:
    return {
        "host": os.getenv("POSTGRES_HOST"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
    }


BA_API_KEY = os.getenv("BA_API_KEY", "jobboerse-jobsuche")
