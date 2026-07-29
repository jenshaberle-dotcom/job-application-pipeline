from pathlib import Path

CHECKLIST = Path("docs/runtime/origin_provider_tools_checklist.md").read_text(
    encoding="utf-8"
)


def test_tools_checklist_covers_runtime_security_prerequisites() -> None:
    required = (
        "private repository",
        "GitHub OIDC",
        "TCP 5432",
        "default_transaction_read_only=on",
        "cannot insert, update or delete",
        "review-only",
    )
    for statement in required:
        assert statement in CHECKLIST


def test_tools_checklist_names_every_required_secret() -> None:
    required_secrets = (
        "TS_OAUTH_CLIENT_ID",
        "TS_AUDIENCE",
        "TAVILY_API_KEY",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
    )
    for secret in required_secrets:
        assert secret in CHECKLIST
