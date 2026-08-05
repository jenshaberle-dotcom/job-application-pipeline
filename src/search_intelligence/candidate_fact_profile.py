from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "candidate_fact_profile.v1"
PROFILE_KEY = "default"
SOURCE_TYPE = "local_private_json"
APPROVAL_TOKEN = "CANDIDATE-FACT-PROFILE-IMPORT-001"

PROFILE_STATUSES = frozenset({"draft", "approved", "superseded"})
FACT_APPROVAL_STATUSES = frozenset(
    {"proposed", "approved", "rejected", "superseded"}
)
CATEGORIES = frozenset(
    {
        "employment",
        "education",
        "skill",
        "project",
        "certification",
        "preference",
        "target_direction",
        "boundary",
    }
)
EVIDENCE_CLASSES = frozenset(
    {
        "professional_employment",
        "formal_education",
        "portfolio_implementation",
        "training_certification",
        "operator_preference",
        "target_direction",
        "planned_capability",
    }
)
PROVENANCE_SOURCE_TYPES = frozenset(
    {
        "operator_assertion",
        "canonical_cv",
        "employment_record",
        "education_record",
        "certificate",
        "repository",
    }
)
CAPABILITY_EVIDENCE_CLASSES = frozenset(
    {
        "professional_employment",
        "formal_education",
        "portfolio_implementation",
        "training_certification",
    }
)
PRODUCTION_EVIDENCE_CLASSES = frozenset({"professional_employment"})
NON_CAPABILITY_EVIDENCE_CLASSES = frozenset(
    {"operator_preference", "target_direction", "planned_capability"}
)

_PROFILE_KEYS = frozenset(
    {
        "schema_version",
        "profile_key",
        "profile_version",
        "status",
        "approved_by",
        "approved_at",
        "facts",
    }
)
_FACT_KEYS = frozenset(
    {
        "fact_key",
        "category",
        "evidence_class",
        "approval_status",
        "statement",
        "capability_tags",
        "limitations",
        "provenance",
        "valid_from",
        "valid_until",
        "approved_by",
        "approved_at",
    }
)
_PROVENANCE_KEYS = frozenset({"source_type", "reference", "observed_at"})
_FACT_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9._+/-]{0,63}$")


@dataclass(frozen=True)
class CandidateFactProvenance:
    source_type: str
    reference: str
    observed_at: str


@dataclass(frozen=True)
class CandidateFact:
    fact_key: str
    category: str
    evidence_class: str
    approval_status: str
    statement: str
    capability_tags: tuple[str, ...]
    limitations: tuple[str, ...]
    provenance: tuple[CandidateFactProvenance, ...]
    valid_from: str | None
    valid_until: str | None
    approved_by: str | None
    approved_at: str | None

    @property
    def is_approved(self) -> bool:
        return self.approval_status == "approved"

    @property
    def is_capability_evidence(self) -> bool:
        return self.is_approved and self.evidence_class in CAPABILITY_EVIDENCE_CLASSES

    @property
    def is_production_evidence(self) -> bool:
        return self.is_approved and self.evidence_class in PRODUCTION_EVIDENCE_CLASSES

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "fact_key": self.fact_key,
            "category": self.category,
            "evidence_class": self.evidence_class,
            "approval_status": self.approval_status,
            "statement": self.statement,
            "capability_tags": list(self.capability_tags),
            "limitations": list(self.limitations),
            "provenance": [asdict(item) for item in self.provenance],
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }


@dataclass(frozen=True)
class CandidateFactProfile:
    schema_version: str
    profile_key: str
    profile_version: str
    status: str
    approved_by: str | None
    approved_at: str | None
    facts: tuple[CandidateFact, ...]

    @property
    def approved_facts(self) -> tuple[CandidateFact, ...]:
        return tuple(fact for fact in self.facts if fact.is_approved)

    @property
    def capability_evidence_facts(self) -> tuple[CandidateFact, ...]:
        return tuple(fact for fact in self.facts if fact.is_capability_evidence)

    @property
    def production_evidence_facts(self) -> tuple[CandidateFact, ...]:
        return tuple(fact for fact in self.facts if fact.is_production_evidence)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "facts": [fact.canonical_payload() for fact in self.facts],
        }

    @property
    def payload_sha256(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()

    @property
    def revision_key(self) -> str:
        return f"{self.profile_version}:{self.payload_sha256[:16]}"

    def redacted_summary(self) -> dict[str, Any]:
        category_counts = Counter(fact.category for fact in self.facts)
        evidence_counts = Counter(fact.evidence_class for fact in self.facts)
        approval_counts = Counter(fact.approval_status for fact in self.facts)
        return {
            "schema_version": self.schema_version,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "status": self.status,
            "payload_sha256": self.payload_sha256,
            "fact_count": len(self.facts),
            "approved_fact_count": len(self.approved_facts),
            "capability_evidence_fact_count": len(self.capability_evidence_facts),
            "production_evidence_fact_count": len(self.production_evidence_facts),
            "category_counts": dict(sorted(category_counts.items())),
            "evidence_class_counts": dict(sorted(evidence_counts.items())),
            "approval_status_counts": dict(sorted(approval_counts.items())),
            "contains_statements": False,
            "contains_provenance_references": False,
        }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    keys = set(value)
    missing = allowed - keys
    extra = keys - allowed
    if missing:
        raise ValueError(f"{label} is missing keys: {sorted(missing)}")
    if extra:
        raise ValueError(f"{label} has unsupported keys: {sorted(extra)}")


def _required_string(value: object, label: str, *, maximum: int = 2000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    result = value.strip()
    if not result:
        raise ValueError(f"{label} must not be blank")
    if len(result) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return result


def _optional_string(value: object, label: str, *, maximum: int = 2000) -> str | None:
    if value is None:
        return None
    return _required_string(value, label, maximum=maximum)


def _parse_datetime(value: object, label: str, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise ValueError(f"{label} is required")
        return None
    text = _required_string(value, label, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.isoformat()


def _parse_date(value: object, label: str) -> str | None:
    if value is None:
        return None
    text = _required_string(value, label, maximum=32)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD") from exc
    return parsed.isoformat()


def _string_array(
    value: object,
    label: str,
    *,
    item_pattern: re.Pattern[str] | None = None,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result: list[str] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item = _required_string(raw, f"{label}[{index}]", maximum=512)
        normalized = item.casefold() if item_pattern is not None else item
        if item_pattern is not None and item_pattern.fullmatch(normalized) is None:
            raise ValueError(f"{label}[{index}] has invalid format")
        if normalized in seen:
            raise ValueError(f"{label} contains duplicate value: {item}")
        seen.add(normalized)
        result.append(normalized if item_pattern is not None else item)
    if not allow_empty and not result:
        raise ValueError(f"{label} must not be empty")
    return tuple(sorted(result)) if item_pattern is not None else tuple(result)


def _parse_provenance(value: object, label: str) -> tuple[CandidateFactProvenance, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty array")
    result: list[CandidateFactProvenance] = []
    seen: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(value):
        item = _mapping(raw, f"{label}[{index}]")
        _exact_keys(item, _PROVENANCE_KEYS, f"{label}[{index}]")
        source_type = _required_string(
            item.get("source_type"), f"{label}[{index}].source_type", maximum=64
        )
        _require(
            source_type in PROVENANCE_SOURCE_TYPES,
            f"{label}[{index}].source_type is unsupported",
        )
        reference = _required_string(
            item.get("reference"), f"{label}[{index}].reference", maximum=1000
        )
        observed_at = _parse_datetime(
            item.get("observed_at"),
            f"{label}[{index}].observed_at",
            required=True,
        )
        assert observed_at is not None
        key = (source_type, reference, observed_at)
        _require(key not in seen, f"{label} contains duplicate provenance")
        seen.add(key)
        result.append(
            CandidateFactProvenance(
                source_type=source_type,
                reference=reference,
                observed_at=observed_at,
            )
        )
    return tuple(sorted(result, key=lambda item: (item.source_type, item.reference, item.observed_at)))


def _validate_evidence_category(fact: CandidateFact) -> None:
    allowed_categories = {
        "professional_employment": {"employment", "skill", "project"},
        "formal_education": {"education", "skill"},
        "portfolio_implementation": {"project", "skill"},
        "training_certification": {"certification", "education", "skill"},
        "operator_preference": {"preference", "boundary"},
        "target_direction": {"target_direction"},
        "planned_capability": {"target_direction", "project", "skill"},
    }
    _require(
        fact.category in allowed_categories[fact.evidence_class],
        f"fact {fact.fact_key} category is incompatible with evidence_class",
    )

    provenance_types = {item.source_type for item in fact.provenance}
    if fact.evidence_class == "portfolio_implementation":
        _require(
            "repository" in provenance_types,
            f"fact {fact.fact_key} portfolio evidence requires repository provenance",
        )
    if fact.evidence_class == "professional_employment":
        _require(
            bool(
                provenance_types
                & {"operator_assertion", "canonical_cv", "employment_record"}
            ),
            f"fact {fact.fact_key} professional evidence requires employment provenance",
        )
    if fact.evidence_class in NON_CAPABILITY_EVIDENCE_CLASSES:
        _require(
            "not_capability_evidence" in fact.limitations,
            f"fact {fact.fact_key} must declare not_capability_evidence",
        )


def _parse_fact(value: object, index: int) -> CandidateFact:
    label = f"facts[{index}]"
    item = _mapping(value, label)
    _exact_keys(item, _FACT_KEYS, label)

    fact_key = _required_string(item.get("fact_key"), f"{label}.fact_key", maximum=128)
    _require(_FACT_KEY_RE.fullmatch(fact_key) is not None, f"{label}.fact_key has invalid format")

    category = _required_string(item.get("category"), f"{label}.category", maximum=64)
    _require(category in CATEGORIES, f"{label}.category is unsupported")

    evidence_class = _required_string(
        item.get("evidence_class"), f"{label}.evidence_class", maximum=64
    )
    _require(evidence_class in EVIDENCE_CLASSES, f"{label}.evidence_class is unsupported")

    approval_status = _required_string(
        item.get("approval_status"), f"{label}.approval_status", maximum=64
    )
    _require(
        approval_status in FACT_APPROVAL_STATUSES,
        f"{label}.approval_status is unsupported",
    )

    approved = approval_status == "approved"
    approved_by = _optional_string(item.get("approved_by"), f"{label}.approved_by", maximum=200)
    approved_at = _parse_datetime(
        item.get("approved_at"), f"{label}.approved_at", required=approved
    )
    if approved:
        _require(approved_by is not None, f"{label}.approved_by is required")
    else:
        _require(
            approved_by is None and approved_at is None,
            f"{label} approval metadata is only allowed for approved facts",
        )

    valid_from = _parse_date(item.get("valid_from"), f"{label}.valid_from")
    valid_until = _parse_date(item.get("valid_until"), f"{label}.valid_until")
    if valid_from is not None and valid_until is not None:
        _require(valid_until >= valid_from, f"{label} validity range is inverted")

    fact = CandidateFact(
        fact_key=fact_key,
        category=category,
        evidence_class=evidence_class,
        approval_status=approval_status,
        statement=_required_string(item.get("statement"), f"{label}.statement"),
        capability_tags=_string_array(
            item.get("capability_tags"),
            f"{label}.capability_tags",
            item_pattern=_TAG_RE,
        ),
        limitations=_string_array(item.get("limitations"), f"{label}.limitations"),
        provenance=_parse_provenance(item.get("provenance"), f"{label}.provenance"),
        valid_from=valid_from,
        valid_until=valid_until,
        approved_by=approved_by,
        approved_at=approved_at,
    )
    _validate_evidence_category(fact)
    return fact


def parse_candidate_fact_profile(value: object) -> CandidateFactProfile:
    payload = _mapping(value, "candidate_fact_profile")
    _exact_keys(payload, _PROFILE_KEYS, "candidate_fact_profile")

    schema_version = _required_string(
        payload.get("schema_version"), "candidate_fact_profile.schema_version", maximum=64
    )
    _require(schema_version == SCHEMA_VERSION, "unsupported candidate fact schema_version")

    profile_key = _required_string(
        payload.get("profile_key"), "candidate_fact_profile.profile_key", maximum=64
    )
    _require(profile_key == PROFILE_KEY, "candidate fact profile_key must be default")

    profile_version = _required_string(
        payload.get("profile_version"),
        "candidate_fact_profile.profile_version",
        maximum=200,
    )
    status = _required_string(
        payload.get("status"), "candidate_fact_profile.status", maximum=64
    )
    _require(status in PROFILE_STATUSES, "unsupported candidate fact profile status")

    approved = status == "approved"
    approved_by = _optional_string(
        payload.get("approved_by"), "candidate_fact_profile.approved_by", maximum=200
    )
    approved_at = _parse_datetime(
        payload.get("approved_at"),
        "candidate_fact_profile.approved_at",
        required=approved,
    )
    if approved:
        _require(approved_by is not None, "approved candidate profile requires approved_by")
    else:
        _require(
            approved_by is None and approved_at is None,
            "profile approval metadata is only allowed for approved status",
        )

    facts_raw = payload.get("facts")
    if not isinstance(facts_raw, list):
        raise ValueError("candidate_fact_profile.facts must be an array")
    facts = tuple(sorted((_parse_fact(item, index) for index, item in enumerate(facts_raw)), key=lambda fact: fact.fact_key))
    fact_keys = [fact.fact_key for fact in facts]
    _require(len(fact_keys) == len(set(fact_keys)), "candidate fact keys must be unique")
    if approved:
        _require(any(fact.is_approved for fact in facts), "approved profile requires at least one approved fact")

    return CandidateFactProfile(
        schema_version=schema_version,
        profile_key=profile_key,
        profile_version=profile_version,
        status=status,
        approved_by=approved_by,
        approved_at=approved_at,
        facts=facts,
    )


def load_candidate_fact_profile_json(text: str) -> CandidateFactProfile:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("candidate fact profile is not valid JSON") from exc
    return parse_candidate_fact_profile(payload)


def candidate_fact_rows(profile: CandidateFactProfile) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for fact in profile.facts:
        payload = fact.canonical_payload()
        rows.append(
            {
                "profile_key": profile.profile_key,
                "fact_key": fact.fact_key,
                "category": fact.category,
                "evidence_class": fact.evidence_class,
                "approval_status": fact.approval_status,
                "statement": fact.statement,
                "capability_tags": list(fact.capability_tags),
                "limitations": list(fact.limitations),
                "provenance": [asdict(item) for item in fact.provenance],
                "valid_from": fact.valid_from,
                "valid_until": fact.valid_until,
                "approved_by": fact.approved_by,
                "approved_at": fact.approved_at,
                "fact_payload": payload,
            }
        )
    return tuple(rows)


def capability_evidence_by_tag(
    profile: CandidateFactProfile,
) -> dict[str, tuple[str, ...]]:
    result: dict[str, list[str]] = {}
    for fact in profile.capability_evidence_facts:
        for tag in fact.capability_tags:
            result.setdefault(tag, []).append(fact.fact_key)
    return {tag: tuple(sorted(keys)) for tag, keys in sorted(result.items())}


def ensure_no_capability_claim_from_direction(
    facts: Sequence[CandidateFact],
) -> None:
    for fact in facts:
        if fact.evidence_class in NON_CAPABILITY_EVIDENCE_CLASSES:
            _require(
                not fact.is_capability_evidence,
                f"non-capability fact became capability evidence: {fact.fact_key}",
            )
