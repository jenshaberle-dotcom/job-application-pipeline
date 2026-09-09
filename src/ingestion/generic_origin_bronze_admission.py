from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from urllib.parse import urlparse

from src.connectors.base import RawJobRecord

GENERIC_SOURCE_PREFIX = "generic_origin:"
BRONZE_ADMISSION_GATE = "generic_origin_job_plausibility_v1"
GENERIC_TITLES = {
    "job",
    "jobs",
    "career",
    "careers",
    "karriere",
    "job detail",
    "job details",
    "job search",
    "jobsuche",
    "stellenangebot",
    "stellenangebote",
}
GENERIC_COMPANIES = {"company", "employer", "arbeitgeber", "unknown", "unbekannt"}


@dataclass(frozen=True)
class BronzeAdmissionDecision:
    passed: bool
    failures: tuple[str, ...]


def _nested_text(data: dict[str, object], *path: str) -> str:
    current: object = data
    for key in path:
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
    return str(current or "").strip()


def evaluate_generic_origin_bronze_record(record: RawJobRecord) -> BronzeAdmissionDecision:
    """Admit only minimally credible generic Employer-Origin job observations.

    Source validity is decided earlier by the generic layer ``proof=PASS`` gate.
    This gate deliberately answers a different question: whether one current
    observation has enough concrete job identity to deserve Bronze persistence.
    A valid active source may therefore emit zero Bronze-admitted jobs.
    """

    failures: list[str] = []
    raw = record.raw_data
    parsed = urlparse(str(record.source_url or ""))

    if not record.source_name.startswith(GENERIC_SOURCE_PREFIX):
        failures.append("not_generic_origin_source")
    if raw.get("source_family") != "generic_origin":
        failures.append("source_family_mismatch")
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        failures.append("non_https_or_missing_job_url")
    if not str(record.external_job_id or "").strip():
        failures.append("missing_external_job_id")

    title = (
        _nested_text(raw, "result_card", "title")
        or _nested_text(raw, "job", "title")
        or _nested_text(raw, "job", "titel")
    )
    if len(title) < 3 or title.casefold() in GENERIC_TITLES:
        failures.append("missing_or_generic_job_title")

    company = (
        _nested_text(raw, "result_card", "company_name")
        or _nested_text(raw, "job", "company_name")
        or _nested_text(raw, "job", "company")
        or _nested_text(raw, "job", "arbeitgeber")
    )
    if len(company) < 2 or company.casefold() in GENERIC_COMPANIES:
        failures.append("missing_or_generic_company")

    detail_url = (
        _nested_text(raw, "result_card", "detail_url")
        or _nested_text(raw, "job", "source_url")
    )
    if not detail_url or detail_url.rstrip("/") != record.source_url.rstrip("/"):
        failures.append("detail_url_identity_mismatch")

    acquisition = raw.get("acquisition_evidence")
    if not isinstance(acquisition, dict):
        failures.append("missing_acquisition_evidence")
    else:
        if acquisition.get("generic_layer_product") is not True:
            failures.append("missing_generic_layer_lineage")
        if not str(acquisition.get("proof_kind") or "").strip():
            failures.append("missing_genuine_job_proof")
        candidate_id = acquisition.get("candidate_id")
        if not isinstance(candidate_id, int) or candidate_id <= 0:
            failures.append("missing_candidate_identity")

    return BronzeAdmissionDecision(not failures, tuple(failures))


def admit_generic_origin_bronze_record(record: RawJobRecord) -> RawJobRecord | None:
    decision = evaluate_generic_origin_bronze_record(record)
    if not decision.passed:
        return None

    raw = deepcopy(record.raw_data)
    raw["bronze_admission"] = {
        "status": "pass",
        "gate": BRONZE_ADMISSION_GATE,
        "source_validity_is_separate": True,
    }
    return RawJobRecord(
        source_name=record.source_name,
        source_url=record.source_url,
        external_job_id=record.external_job_id,
        raw_data=raw,
    )


def filter_generic_origin_bronze_records(
    records: list[RawJobRecord],
) -> list[RawJobRecord]:
    admitted: list[RawJobRecord] = []
    for record in records:
        value = admit_generic_origin_bronze_record(record)
        if value is not None:
            admitted.append(value)
    return admitted
