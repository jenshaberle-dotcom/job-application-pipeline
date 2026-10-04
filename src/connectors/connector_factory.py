from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import IntEnum, StrEnum
from urllib.parse import urlsplit, urlunsplit

FACTORY_SCHEMA_VERSION = "jap.connector_factory.v1"
RECIPE_SCHEMA_VERSION = "jap.connector_recipe.v1"
INSTANCE_SCHEMA_VERSION = "jap.connector_instance.v1"
QUALIFICATION_SCHEMA_VERSION = "jap.connector_qualification.v1"
CATALOG_SCHEMA_VERSION = "jap.connector_capability_catalog.v1"
QUALIFIER_VERSION = 1
EMPLOYER_ORIGIN_SOURCE_TYPES = frozenset(
    {
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
)


class FactoryDisposition(StrEnum):
    RECIPE_READY = "recipe_ready"
    CAPABILITY_GAP = "capability_gap"
    EVIDENCE_GAP = "evidence_gap"


class ConnectorCapabilityRole(StrEnum):
    ORIGIN_INVENTORY = "origin_inventory"
    JOB_DETAIL = "job_detail"
    DELEGATION = "delegation"


class ReuseTier(IntEnum):
    GENERIC_ORIGIN = 0
    PROVIDER_FAMILY = 1
    REUSABLE_EXTENSION = 2


@dataclass(frozen=True, slots=True)
class CandidateConnectorEvidence:
    candidate_key: str
    company_key: str
    origin_url: str
    source_type: str
    required_roles: tuple[ConnectorCapabilityRole, ...]
    fingerprint_tags: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    market_sensor_only: bool = False

    def __post_init__(self) -> None:
        if not self.candidate_key.strip():
            raise ValueError("candidate_key_required")
        if not self.company_key.strip():
            raise ValueError("company_key_required")
        if not self.source_type.strip():
            raise ValueError("source_type_required")
        if not self.required_roles:
            raise ValueError("required_roles_required")


@dataclass(frozen=True, slots=True)
class ConnectorFactoryCapability:
    capability_id: str
    version: int
    roles: tuple[ConnectorCapabilityRole, ...]
    reuse_tier: ReuseTier
    required_fingerprint_tags: tuple[str, ...] = ()
    priority: int = 100
    enabled: bool = True
    runtime_strategy: str = "UNIMPLEMENTED"

    def __post_init__(self) -> None:
        if not self.capability_id.strip():
            raise ValueError("capability_id_required")
        if self.version < 1:
            raise ValueError("capability_version_invalid")
        if not self.roles:
            raise ValueError("capability_roles_required")
        if self.priority < 0:
            raise ValueError("capability_priority_invalid")
        if self.runtime_strategy not in {"UNIMPLEMENTED", "JSON_API", "JSONLD", "HTML_DETAIL"}:
            raise ValueError("capability_runtime_strategy_invalid")


@dataclass(frozen=True, slots=True)
class RecipeBinding:
    role: ConnectorCapabilityRole
    capability_id: str
    capability_version: int


@dataclass(frozen=True, slots=True)
class ConnectorRecipe:
    schema_version: str
    recipe_id: str
    recipe_version: int
    company_key: str
    origin_url: str
    source_type: str
    bindings: tuple[RecipeBinding, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConnectorFactoryResult:
    schema_version: str
    disposition: FactoryDisposition
    recipe: ConnectorRecipe | None
    missing_roles: tuple[ConnectorCapabilityRole, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class ConnectorInstance:
    schema_version: str
    instance_id: str
    company_key: str
    source_name: str
    recipe_id: str
    recipe_version: int
    qualification_proof_id: str
    lifecycle_state: str = "QUALIFIED_INACTIVE"


@dataclass(frozen=True, slots=True)
class ConnectorQualificationProof:
    schema_version: str
    qualifier_version: int
    proof_id: str
    recipe_id: str
    recipe_version: int
    recipe_schema_version: str
    recipe_content_digest: str
    catalog_schema_version: str
    catalog_content_digest: str
    capabilities: tuple[ConnectorFactoryCapability, ...]
    source_type: str
    origin_url: str
    evidence_ids: tuple[str, ...]
    status: str
    blockers: tuple[str, ...]


def _content_digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def qualify_connector_recipe(
    recipe: ConnectorRecipe,
    capabilities: tuple[ConnectorFactoryCapability, ...],
) -> ConnectorQualificationProof:
    """Check definition integrity only; PASS grants no acquisition or runtime authority."""
    catalog = tuple(sorted(capabilities, key=lambda item: _content_digest(asdict(item))))
    blockers: set[str] = set()
    if recipe.schema_version != RECIPE_SCHEMA_VERSION or recipe.recipe_version != 1:
        blockers.add("recipe_schema_or_version_invalid")
    if recipe.recipe_id != _recipe_id(
        company_key=recipe.company_key,
        origin_url=recipe.origin_url,
        source_type=recipe.source_type,
        bindings=recipe.bindings,
    ):
        blockers.add("recipe_identity_mismatch")
    try:
        if _canonical_origin_url(recipe.origin_url) != recipe.origin_url:
            blockers.add("origin_identity_not_normalized")
    except ValueError:
        blockers.add("origin_identity_invalid")
    if not recipe.company_key or _clean_text(recipe.company_key).casefold() != recipe.company_key:
        blockers.add("company_identity_not_normalized")
    if recipe.source_type not in EMPLOYER_ORIGIN_SOURCE_TYPES:
        blockers.add("source_type_not_employer_origin")
    if not recipe.evidence_ids or recipe.evidence_ids != _canonical_evidence_ids(
        recipe.evidence_ids
    ):
        blockers.add("evidence_lineage_invalid")
    roles = tuple(binding.role for binding in recipe.bindings)
    if not roles or len(set(roles)) != len(roles):
        blockers.add("recipe_roles_empty_or_duplicate")
    if tuple(sorted(recipe.bindings, key=lambda item: item.role.value)) != recipe.bindings:
        blockers.add("recipe_bindings_not_normalized")
    for binding in recipe.bindings:
        matches = [
            item
            for item in catalog
            if (
                item.capability_id == binding.capability_id
                and item.version == binding.capability_version
            )
        ]
        if len(matches) != 1:
            blockers.add("capability_binding_missing_or_ambiguous")
        elif binding.role not in matches[0].roles:
            blockers.add("capability_role_mismatch")
        elif matches[0].enabled is not True:
            blockers.add("capability_disabled")
    payload = {
        "schema_version": QUALIFICATION_SCHEMA_VERSION,
        "qualifier_version": QUALIFIER_VERSION,
        "recipe_id": recipe.recipe_id,
        "recipe_version": recipe.recipe_version,
        "recipe_schema_version": recipe.schema_version,
        "recipe_content_digest": _content_digest(asdict(recipe)),
        "catalog_schema_version": CATALOG_SCHEMA_VERSION,
        "catalog_content_digest": _content_digest(
            {
                "schema_version": CATALOG_SCHEMA_VERSION,
                "capabilities": [asdict(item) for item in catalog],
            }
        ),
        "capabilities": catalog,
        "source_type": recipe.source_type,
        "origin_url": recipe.origin_url,
        "evidence_ids": recipe.evidence_ids,
        "status": "FAIL" if blockers else "PASS",
        "blockers": tuple(sorted(blockers)),
    }
    digest_payload = {**payload, "capabilities": [asdict(item) for item in catalog]}
    return ConnectorQualificationProof(proof_id=_content_digest(digest_payload), **payload)


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _canonical_tags(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({_clean_text(value).casefold() for value in values if _clean_text(value)}))


def _canonical_evidence_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({_clean_text(value) for value in values if _clean_text(value)}))


def _canonical_origin_url(value: str) -> str:
    text = value.strip()
    parsed = urlsplit(text)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("origin_url_invalid")
    if parsed.username or parsed.password:
        raise ValueError("origin_url_credentials_forbidden")
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.query,
            "",
        )
    )


def _recipe_id(
    *,
    company_key: str,
    origin_url: str,
    source_type: str,
    bindings: tuple[RecipeBinding, ...],
) -> str:
    canonical = {
        "schema_version": RECIPE_SCHEMA_VERSION,
        "recipe_version": 1,
        "company_key": company_key,
        "origin_url": origin_url,
        "source_type": source_type,
        "bindings": [
            {
                "role": binding.role.value,
                "capability_id": binding.capability_id,
                "capability_version": binding.capability_version,
            }
            for binding in bindings
        ],
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _eligible_capabilities(
    role: ConnectorCapabilityRole,
    fingerprint_tags: tuple[str, ...],
    capabilities: tuple[ConnectorFactoryCapability, ...],
) -> tuple[ConnectorFactoryCapability, ...]:
    observed = set(fingerprint_tags)
    eligible = []
    for capability in capabilities:
        if not capability.enabled or role not in capability.roles:
            continue
        required = set(_canonical_tags(capability.required_fingerprint_tags))
        if required.issubset(observed):
            eligible.append(capability)
    return tuple(
        sorted(
            eligible,
            key=lambda item: (
                item.priority,
                int(item.reuse_tier),
                item.capability_id,
                item.version,
            ),
        )
    )


def capabilities_from_catalog(payload: dict[str, object]) -> tuple[ConnectorFactoryCapability, ...]:
    if payload.get("schema_version") != "jap.connector_capability_catalog.v1":
        raise ValueError("capability_catalog_schema_invalid")
    raw = payload.get("capabilities")
    if not isinstance(raw, list) or not raw:
        raise ValueError("capability_catalog_empty")

    capabilities: list[ConnectorFactoryCapability] = []
    seen: set[tuple[str, int]] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("capability_catalog_item_invalid")
        capability_id = _clean_text(str(item.get("capability_id") or ""))
        version = item.get("version")
        if not isinstance(version, int) or isinstance(version, bool):
            raise TypeError("capability_catalog_version_invalid")
        identity = (capability_id, version)
        if identity in seen:
            raise ValueError("capability_catalog_duplicate_identity")
        seen.add(identity)

        roles_raw = item.get("roles")
        if not isinstance(roles_raw, list) or not roles_raw:
            raise ValueError("capability_catalog_roles_invalid")
        tags_raw = item.get("required_fingerprint_tags", [])
        if not isinstance(tags_raw, list):
            raise TypeError("capability_catalog_tags_invalid")

        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            raise TypeError("capability_catalog_enabled_invalid")
        priority = item.get("priority", 100)
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise TypeError("capability_catalog_priority_invalid")

        capabilities.append(
            ConnectorFactoryCapability(
                capability_id=capability_id,
                version=version,
                roles=tuple(ConnectorCapabilityRole(str(value)) for value in roles_raw),
                reuse_tier=ReuseTier[str(item.get("reuse_tier") or "")],
                required_fingerprint_tags=tuple(str(value) for value in tags_raw),
                priority=priority,
                enabled=enabled,
                runtime_strategy=str(item.get("runtime_strategy", "UNIMPLEMENTED")),
            )
        )

    return tuple(capabilities)


def compile_connector_recipe(
    evidence: CandidateConnectorEvidence,
    capabilities: tuple[ConnectorFactoryCapability, ...],
) -> ConnectorFactoryResult:
    if evidence.market_sensor_only:
        return ConnectorFactoryResult(
            schema_version=FACTORY_SCHEMA_VERSION,
            disposition=FactoryDisposition.EVIDENCE_GAP,
            recipe=None,
            missing_roles=(),
            reason="market_sensor_not_employer_source_authority",
        )

    source_type = _clean_text(evidence.source_type).casefold()
    if source_type not in EMPLOYER_ORIGIN_SOURCE_TYPES:
        return ConnectorFactoryResult(
            schema_version=FACTORY_SCHEMA_VERSION,
            disposition=FactoryDisposition.EVIDENCE_GAP,
            recipe=None,
            missing_roles=(),
            reason="source_type_not_employer_origin",
        )

    evidence_ids = _canonical_evidence_ids(evidence.evidence_ids)
    if not evidence_ids:
        return ConnectorFactoryResult(
            schema_version=FACTORY_SCHEMA_VERSION,
            disposition=FactoryDisposition.EVIDENCE_GAP,
            recipe=None,
            missing_roles=(),
            reason="candidate_evidence_required",
        )

    origin_url = _canonical_origin_url(evidence.origin_url)
    fingerprint_tags = _canonical_tags(evidence.fingerprint_tags)
    if not fingerprint_tags:
        return ConnectorFactoryResult(
            schema_version=FACTORY_SCHEMA_VERSION,
            disposition=FactoryDisposition.EVIDENCE_GAP,
            recipe=None,
            missing_roles=(),
            reason="origin_fingerprint_required",
        )

    roles = tuple(sorted(set(evidence.required_roles), key=lambda item: item.value))
    selected: list[RecipeBinding] = []
    missing: list[ConnectorCapabilityRole] = []

    for role in roles:
        eligible = _eligible_capabilities(role, fingerprint_tags, capabilities)
        if not eligible:
            missing.append(role)
            continue
        capability = eligible[0]
        selected.append(
            RecipeBinding(
                role=role,
                capability_id=capability.capability_id,
                capability_version=capability.version,
            )
        )

    if missing:
        return ConnectorFactoryResult(
            schema_version=FACTORY_SCHEMA_VERSION,
            disposition=FactoryDisposition.CAPABILITY_GAP,
            recipe=None,
            missing_roles=tuple(missing),
            reason="required_capability_not_representable",
        )

    bindings = tuple(selected)
    company_key = _clean_text(evidence.company_key).casefold()
    recipe = ConnectorRecipe(
        schema_version=RECIPE_SCHEMA_VERSION,
        recipe_id=_recipe_id(
            company_key=company_key,
            origin_url=origin_url,
            source_type=source_type,
            bindings=bindings,
        ),
        recipe_version=1,
        company_key=company_key,
        origin_url=origin_url,
        source_type=source_type,
        bindings=bindings,
        evidence_ids=evidence_ids,
    )
    return ConnectorFactoryResult(
        schema_version=FACTORY_SCHEMA_VERSION,
        disposition=FactoryDisposition.RECIPE_READY,
        recipe=recipe,
        missing_roles=(),
        reason="all_required_roles_reused_from_catalog",
    )


def materialize_qualified_connector_instance(
    recipe: ConnectorRecipe,
    *,
    qualification_proof: ConnectorQualificationProof,
) -> ConnectorInstance:
    if not isinstance(qualification_proof, ConnectorQualificationProof):
        raise TypeError("qualification_proof_object_required")
    if qualification_proof.status != "PASS":
        raise ValueError("qualification_pass_required")
    if qualify_connector_recipe(recipe, qualification_proof.capabilities) != qualification_proof:
        raise ValueError("qualification_proof_binding_mismatch")

    source_name = f"generic_origin:{recipe.company_key}"
    payload = json.dumps(
        {
            "schema_version": INSTANCE_SCHEMA_VERSION,
            "company_key": recipe.company_key,
            "source_name": source_name,
            "recipe_id": recipe.recipe_id,
            "recipe_version": recipe.recipe_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return ConnectorInstance(
        schema_version=INSTANCE_SCHEMA_VERSION,
        instance_id=hashlib.sha256(payload).hexdigest(),
        company_key=recipe.company_key,
        source_name=source_name,
        recipe_id=recipe.recipe_id,
        recipe_version=recipe.recipe_version,
        qualification_proof_id=qualification_proof.proof_id,
    )


def connector_factory_evidence_records(
    recipe: ConnectorRecipe,
    qualification_proof: ConnectorQualificationProof,
) -> dict[str, dict[str, object]]:
    """Build canonical insert records without opening a database connection.

    A repeated identity must be compared with stored content by the future writer;
    it must never be implemented as an UPDATE/upsert of immutable evidence.
    """
    instance = materialize_qualified_connector_instance(
        recipe, qualification_proof=qualification_proof
    )
    definition = asdict(recipe)
    # Evidence belongs to each proof, not the reusable recipe identity.
    del definition["evidence_ids"]

    def canonical_json(payload: object) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    return {
        "recipe": {
            "recipe_id": recipe.recipe_id,
            "recipe_version": recipe.recipe_version,
            "schema_version": recipe.schema_version,
            "definition_json": canonical_json(definition),
        },
        "qualification": {
            "proof_id": qualification_proof.proof_id,
            "recipe_id": recipe.recipe_id,
            "recipe_version": recipe.recipe_version,
            "qualification_status": "PASS",
            "proof_json": canonical_json(asdict(qualification_proof)),
        },
        "instance": {
            "instance_id": instance.instance_id,
            "recipe_id": recipe.recipe_id,
            "recipe_version": recipe.recipe_version,
            "qualification_proof_id": qualification_proof.proof_id,
            "qualification_status": "PASS",
            "lifecycle_state": instance.lifecycle_state,
            "definition_json": canonical_json(asdict(instance)),
        },
    }
