from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

BA_SOURCE_NAME = "bundesagentur_fuer_arbeit"
BA_LOCAL_PROFILE_NAME = "ba_data_engineer_30629_50km"
BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME = "ba_data_engineering_remote_nationwide_review"
EXPECTED_BA_REMOTE_TERMS = (
    "Data Engineer",
    "Analytics Engineer",
    "Big Data",
    "Data Platform",
    "Data Warehouse",
    "ETL",
    "Python SQL",
)


@dataclass(frozen=True)
class MarketSensorProfileState:
    id: int
    profile_name: str
    source_name: str
    search_term: str | None
    search_location: str | None
    search_radius_km: int | None
    offer_type: int | None
    page_size: int
    is_active: bool

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "MarketSensorProfileState":
        return cls(
            id=int(row["id"]),
            profile_name=str(row["profile_name"]),
            source_name=str(row["source_name"]),
            search_term=_optional_text(row.get("search_term")),
            search_location=_optional_text(row.get("search_location")),
            search_radius_km=_optional_int(row.get("search_radius_km")),
            offer_type=_optional_int(row.get("offer_type")),
            page_size=int(row["page_size"]),
            is_active=bool(row["is_active"]),
        )


@dataclass(frozen=True)
class MarketSensorTermState:
    profile_name: str
    search_term: str
    is_active: bool

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "MarketSensorTermState":
        return cls(
            profile_name=str(row["profile_name"]),
            search_term=str(row["search_term"]),
            is_active=bool(row["is_active"]),
        )


@dataclass(frozen=True)
class ControlledActivationReview:
    overall_status: str
    current_profiles: tuple[MarketSensorProfileState, ...]
    current_terms: tuple[MarketSensorTermState, ...]
    expected_review_profile_name: str
    expected_terms: tuple[str, ...]
    findings: tuple[str, ...]
    next_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "sensor001c.ba_remote_nationwide_controlled_activation.v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "work_item": "SENSOR-001C BA Remote/Nationwide Controlled Activation",
            "source_name": BA_SOURCE_NAME,
            "generic_requirement": (
                "Every market sensor must make local/regional coverage and Germany-wide "
                "remote-option coverage explicit. Controlled activation must keep review "
                "profiles inactive until a separate approval gate promotes them."
            ),
            "safety_boundary": {
                "read_only_review_script": True,
                "migration_creates_inactive_review_profile": True,
                "external_requests": False,
                "ingestion_run": False,
                "scheduler_mutation": False,
                "connector_activation": False,
                "candidate_or_gate_mutation": False,
                "productive_activation": False,
            },
            "overall_status": self.overall_status,
            "current_profiles": [asdict(profile) for profile in self.current_profiles],
            "current_terms": [asdict(term) for term in self.current_terms],
            "expected_review_profile_name": self.expected_review_profile_name,
            "expected_terms": list(self.expected_terms),
            "findings": list(self.findings),
            "next_action": self.next_action,
        }


def build_ba_remote_controlled_activation_review(
    profiles: Iterable[MarketSensorProfileState],
    terms: Iterable[MarketSensorTermState],
) -> ControlledActivationReview:
    profile_tuple = tuple(profile for profile in profiles if profile.source_name == BA_SOURCE_NAME)
    term_tuple = tuple(terms)

    review_profiles = tuple(
        profile
        for profile in profile_tuple
        if profile.profile_name == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME
    )
    local_profiles = tuple(
        profile
        for profile in profile_tuple
        if profile.profile_name == BA_LOCAL_PROFILE_NAME
    )

    findings: list[str] = []
    if not local_profiles:
        findings.append("Existing local BA Hannover/50km baseline profile was not found.")

    if not review_profiles:
        findings.append("Remote/nationwide review profile is not present yet; migration is pending.")
        return ControlledActivationReview(
            overall_status="migration_pending",
            current_profiles=profile_tuple,
            current_terms=term_tuple,
            expected_review_profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            expected_terms=EXPECTED_BA_REMOTE_TERMS,
            findings=tuple(findings),
            next_action=(
                "Apply the reviewed SENSOR-001C migration to create the inactive review profile, "
                "then rerun this read-only review."
            ),
        )

    if len(review_profiles) > 1:
        findings.append("More than one BA remote/nationwide review profile exists.")
        return ControlledActivationReview(
            overall_status="duplicate_review_profile_detected",
            current_profiles=profile_tuple,
            current_terms=term_tuple,
            expected_review_profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            expected_terms=EXPECTED_BA_REMOTE_TERMS,
            findings=tuple(findings),
            next_action="Stop and resolve duplicate profile state before any activation.",
        )

    review_profile = review_profiles[0]
    review_terms = tuple(
        term.search_term
        for term in term_tuple
        if term.profile_name == BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME and term.is_active
    )

    if review_profile.is_active:
        findings.append("Remote/nationwide review profile is active; this is not allowed in SENSOR-001C.")
        return ControlledActivationReview(
            overall_status="unsafe_active_profile_detected",
            current_profiles=profile_tuple,
            current_terms=term_tuple,
            expected_review_profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            expected_terms=EXPECTED_BA_REMOTE_TERMS,
            findings=tuple(findings),
            next_action="Deactivate the review profile or stop and inspect before any scheduled ingestion.",
        )

    if review_profile.search_location is not None or review_profile.search_radius_km is not None:
        findings.append("Review profile does not use NULL location/radius for nationwide review semantics.")

    missing_terms = tuple(term for term in EXPECTED_BA_REMOTE_TERMS if term not in review_terms)
    if missing_terms:
        findings.append("Review profile is missing expected terms: " + ", ".join(missing_terms))

    if findings:
        return ControlledActivationReview(
            overall_status="configuration_mismatch",
            current_profiles=profile_tuple,
            current_terms=term_tuple,
            expected_review_profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
            expected_terms=EXPECTED_BA_REMOTE_TERMS,
            findings=tuple(findings),
            next_action="Repair the inactive review profile configuration before considering activation.",
        )

    findings.append("Inactive BA remote/nationwide review profile exists with expected terms.")
    findings.append("Existing local Hannover/50km BA profile remains separate.")

    return ControlledActivationReview(
        overall_status="review_profile_ready",
        current_profiles=profile_tuple,
        current_terms=term_tuple,
        expected_review_profile_name=BA_REMOTE_NATIONWIDE_REVIEW_PROFILE_NAME,
        expected_terms=EXPECTED_BA_REMOTE_TERMS,
        findings=tuple(findings),
        next_action=(
            "Run a separate bounded sample-ingestion review before any productive activation. "
            "Do not activate scheduler coverage automatically."
        ),
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SENSOR-001C BA Remote/Nationwide Controlled Activation Review",
        "",
        f"- overall_status: `{report.get('overall_status')}`",
        f"- source_name: `{report.get('source_name')}`",
        f"- generated_at_utc: `{report.get('generated_at_utc')}`",
        "",
        "## Findings",
        "",
    ]
    for finding in report.get("findings", []):
        lines.append(f"- {finding}")

    lines.extend(
        [
            "",
            "## Next action",
            "",
            str(report.get("next_action", "")),
            "",
            "## Safety boundary",
            "",
        ]
    )
    for key, value in report.get("safety_boundary", {}).items():
        lines.append(f"- {key}: `{value}`")

    lines.append("")
    return "\n".join(lines)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
