from pathlib import Path

CHECKLIST = Path("docs/guides/origin_provider_tools_checklist.md").read_text(
    encoding="utf-8"
)


def test_tools_checklist_covers_runtime_security_prerequisites() -> None:
    checklist = CHECKLIST.lower()
    required = (
        "private repository",
        "github oidc",
        "tcp 5432",
        "default_transaction_read_only=on",
        "cannot insert, update or delete",
        "review-only",
    )
    for statement in required:
        assert statement in checklist


def test_tools_checklist_names_every_required_secret() -> None:
    required_secrets = (
        "TS_OAUTH_CLIENT_ID",
        "TS_AUDIENCE",
        "TAVILY_API_KEY",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "ORIGIN_BENCHMARK_DB_USER",
        "ORIGIN_BENCHMARK_DB_PASSWORD",
    )
    for secret in required_secrets:
        assert secret in CHECKLIST


def test_tools_checklist_rejects_generic_reader_credential_names() -> None:
    assert "`POSTGRES_USER` and `POSTGRES_PASSWORD`" in CHECKLIST
    assert "must not use those generic names" in CHECKLIST
