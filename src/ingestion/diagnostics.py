from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET

import psycopg
import requests


@dataclass(frozen=True)
class IngestionFailureDiagnostic:
    error_type: str
    error_stage: str
    error_message: str
    suggested_action: str


def classify_exception(
    exc: Exception,
    error_stage: str,
) -> IngestionFailureDiagnostic:
    error_type = "unknown_error"
    suggested_action = "Inspect the exception message and connector implementation."

    if isinstance(exc, requests.Timeout):
        error_type = "network_timeout"
        suggested_action = "Retry later and verify whether the source endpoint is reachable."
    elif isinstance(exc, requests.HTTPError):
        error_type = "http_error"
        suggested_action = "Verify the source target, endpoint URL and HTTP response status."
    elif isinstance(exc, requests.RequestException):
        error_type = "network_error"
        suggested_action = "Check network connectivity and source endpoint availability."
    elif isinstance(exc, ET.ParseError):
        error_type = "parse_error"
        suggested_action = "Inspect the source response format and parser assumptions."
    elif isinstance(exc, psycopg.Error):
        error_type = "database_error"
        suggested_action = "Inspect database connectivity, schema state and SQL constraints."
    elif isinstance(exc, (KeyError, ValueError, TypeError)):
        error_type = "validation_error"
        suggested_action = "Inspect connector configuration, expected fields and input data."

    message = f"{type(exc).__name__}: {exc}".strip()

    return IngestionFailureDiagnostic(
        error_type=error_type,
        error_stage=error_stage,
        error_message=message,
        suggested_action=suggested_action,
    )


def format_ingestion_failure(
    profile_name: str,
    source_name: str,
    diagnostic: IngestionFailureDiagnostic,
) -> str:
    return "\n".join(
        [
            f"✗ Failed ingestion profile: {profile_name}",
            f"  Source: {source_name}",
            f"  Stage: {diagnostic.error_stage}",
            f"  Type: {diagnostic.error_type}",
            f"  Message: {diagnostic.error_message}",
            f"  Suggested action: {diagnostic.suggested_action}",
        ]
    )
