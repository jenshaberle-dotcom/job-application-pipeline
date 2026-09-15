from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from src.silver.external_observer_contract import (
    ExternalObserverError,
    run_external_skill_observer,
    validate_external_skill_payload,
)


def test_external_skill_payload_accepts_only_exact_origin_spans() -> None:
    text = "Erfahrung mit EBICS Zahlungsverkehr und agilen Methoden ist erwünscht."
    start = text.index("EBICS Zahlungsverkehr")
    end = start + len("EBICS Zahlungsverkehr")
    result = validate_external_skill_payload(
        text=text,
        observer_name="shadow",
        payload={
            "observations": [
                {
                    "field": "skills",
                    "value": "electronic banking",
                    "evidence": text[start:end],
                    "start": start,
                    "end": end,
                },
                {
                    "field": "skills",
                    "value": "invented skill",
                    "evidence": "invented skill",
                    "start": 0,
                    "end": 14,
                },
            ]
        },
    )

    assert result.proposed_count == 2
    assert result.rejected_count == 1
    assert len(result.facts) == 1
    fact = result.facts[0]
    assert fact.field == "skills"
    assert fact.value == "EBICS Zahlungsverkehr"
    assert fact.evidence == "EBICS Zahlungsverkehr"
    assert fact.basis == "external_shadow:shadow"


def test_external_normalized_value_never_becomes_jap_fact_value() -> None:
    text = "Kenntnisse in agilen Methoden sind erforderlich."
    start = text.index("agilen Methoden")
    end = start + len("agilen Methoden")
    result = validate_external_skill_payload(
        text=text,
        observer_name="taxonomy-linker",
        payload={
            "observations": [
                {
                    "field": "skills",
                    "value": "agile project management",
                    "evidence": text[start:end],
                    "start": start,
                    "end": end,
                }
            ]
        },
    )

    assert result.facts[0].value == "agilen Methoden"
    assert result.facts[0].value != "agile project management"


def test_subprocess_observer_is_optional_and_fail_closed(tmp_path: Path) -> None:
    helper = tmp_path / "observer.py"
    helper.write_text(
        "import json,sys\n"
        "request=json.loads(sys.stdin.read())\n"
        "text=request['text']\n"
        "start=text.index('Terraform')\n"
        "print(json.dumps({'observations':[{'field':'skills','value':'terraform','evidence':text[start:start+9],'start':start,'end':start+9}]}))\n",
        encoding="utf-8",
    )
    result = run_external_skill_observer(
        command=(sys.executable, str(helper)),
        text="AWS und Terraform werden vorausgesetzt.",
        observer_name="fixture",
    )
    assert [fact.evidence for fact in result.facts] == ["Terraform"]

    with pytest.raises(ExternalObserverError):
        run_external_skill_observer(
            command=(sys.executable, "-c", "raise SystemExit(3)"),
            text="Python",
            observer_name="broken",
        )
