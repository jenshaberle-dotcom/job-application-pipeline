import xml.etree.ElementTree as ET

import requests

from src.ingestion.diagnostics import classify_exception, format_ingestion_failure


def test_classifies_timeout_as_network_timeout() -> None:
    diagnostic = classify_exception(
        exc=requests.Timeout("request timed out"),
        error_stage="source_request",
    )

    assert diagnostic.error_type == "network_timeout"
    assert diagnostic.error_stage == "source_request"
    assert "Timeout" in diagnostic.error_message
    assert "Retry" in diagnostic.suggested_action


def test_classifies_xml_parse_error_as_parse_error() -> None:
    diagnostic = classify_exception(
        exc=ET.ParseError("invalid XML"),
        error_stage="parse",
    )

    assert diagnostic.error_type == "parse_error"
    assert diagnostic.error_stage == "parse"
    assert "invalid XML" in diagnostic.error_message


def test_formats_human_readable_ingestion_failure() -> None:
    diagnostic = classify_exception(
        exc=requests.HTTPError("404 Client Error"),
        error_stage="source_request",
    )

    message = format_ingestion_failure(
        profile_name="personio_loyos_bi_data_engineer",
        source_name="personio:loyos-bi",
        diagnostic=diagnostic,
    )

    assert "Failed ingestion profile: personio_loyos_bi_data_engineer" in message
    assert "Source: personio:loyos-bi" in message
    assert "Stage: source_request" in message
    assert "Type: http_error" in message
    assert "Suggested action:" in message
