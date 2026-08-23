from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import PurePosixPath
from typing import Any, Final, Mapping


TRANSPORT_PLATFORM: Final[str] = "kaggle"
TRAINING_PACKAGE_SCHEMA_VERSION: Final[str] = "ml-training-package/v1"
CPU_VALIDATION_COMPUTE_CLASS: Final[str] = "cpu_validation"
GPU_TRAINING_COMPUTE_CLASS: Final[str] = "gpu_training"

PACKAGE_ENTRY_ROLES: Final[frozenset[str]] = frozenset(
    {"dataset_payload", "dataset_manifest", "snapshot_metadata"}
)
REQUIRED_PACKAGE_ENTRY_ROLES: Final[frozenset[str]] = frozenset(
    {"dataset_payload", "dataset_manifest"}
)
TELEMETRY_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        "quota_before",
        "provider_status",
        "epoch_checkpoint",
        "artifact_inventory",
        "quota_after",
        "terminal_state",
        "diagnostic",
    }
)
CHECKPOINT_STATES: Final[frozenset[str]] = frozenset(
    {"checkpoint_complete", "run_complete", "failed"}
)
DIAGNOSTIC_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "hypothesis_failure",
        "convergence_failure",
        "operational_failure",
        "governance_failure",
    }
)


@dataclass(frozen=True)
class KaggleTransportPolicy:
    cpu_validation_allowed: bool = True
    external_upload_authorized: bool = False
    gpu_training_authorized: bool = False
    provider_credentials_in_repository: bool = False
    observer_owns_provider_lifetime: bool = False
    quota_snapshots_required: bool = True
    artifact_inventory_required: bool = True
    checkpoint_reentry_required: bool = True
    reuse_unchanged_provider_capability_evidence: bool = True
    inaccessible_status_failures_before_abort: int = 3


@dataclass(frozen=True)
class TrainingPackageEntry:
    role: str
    name: str
    content_fingerprint: str
    size_bytes: int


@dataclass(frozen=True)
class TrainingPackageManifest:
    package_id: str
    dataset_manifest_fingerprint: str
    snapshot_plan_fingerprint: str
    source_snapshot: str
    feature_contract_version: str
    product_contract_version: str
    code_commit: str
    entries: tuple[TrainingPackageEntry, ...]
    transport_platform: str = TRANSPORT_PLATFORM
    schema_version: str = TRAINING_PACKAGE_SCHEMA_VERSION


@dataclass(frozen=True)
class CpuValidationReport:
    package_fingerprint: str
    checked_entries: tuple[str, ...]
    compute_class: str = CPU_VALIDATION_COMPUTE_CLASS
    external_execution: bool = False
    product_authority: bool = False

    def __post_init__(self) -> None:
        if self.compute_class != CPU_VALIDATION_COMPUTE_CLASS:
            raise ValueError("CPU validation must use the cpu_validation compute class.")
        if self.external_execution:
            raise ValueError("MLF-004 CPU validation must remain local or CI-only.")
        if self.product_authority:
            raise ValueError("MLF-004 validation output may not claim product authority.")


@dataclass(frozen=True)
class ExperimentComputeIntent:
    experiment_id: str
    training_package_fingerprint: str
    compute_class: str
    external_execution: bool
    operator_authorization_reference: str = ""


@dataclass(frozen=True)
class ComputeAdmission:
    allowed: bool
    operator_authorization_required: bool
    reason: str


@dataclass(frozen=True)
class ExperimentArtifactMetadata:
    artifact_id: str
    experiment_id: str
    training_package_fingerprint: str
    artifact_kind: str
    content_fingerprint: str
    code_commit: str
    compute_class: str
    operator_authorization_reference: str = ""
    product_authority: bool = False


@dataclass(frozen=True)
class ExperimentTelemetryEvent:
    experiment_id: str
    training_package_fingerprint: str
    event_type: str
    observed_at_utc: str
    compute_class: str
    provider_run_reference: str = ""
    epoch: int | None = None
    details_fingerprint: str = ""
    product_authority: bool = False


@dataclass(frozen=True)
class EpochReentryCheckpoint:
    experiment_id: str
    training_package_fingerprint: str
    epoch_completed: int
    checkpoint_artifact_fingerprint: str
    metrics_fingerprint: str
    code_commit: str
    provider_run_reference: str
    operator_authorization_reference: str
    state: str = "checkpoint_complete"
    resume_parent_fingerprint: str = ""
    product_authority: bool = False


@dataclass(frozen=True)
class DiagnosticReceipt:
    experiment_id: str
    stage: str
    failure_class: str
    evidence_key: str
    details_fingerprint: str
    provider_run_reference: str = ""
    product_authority: bool = False


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def fingerprint_bytes(content: bytes) -> str:
    return f"sha256:{sha256(content).hexdigest()}"


def _is_sha256_fingerprint(value: str) -> bool:
    if not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )


def _is_utc_timestamp(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == UTC.utcoffset(parsed)


def _is_safe_package_name(value: str) -> bool:
    if not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and path.name == value


def validate_kaggle_transport_policy(policy: KaggleTransportPolicy) -> list[str]:
    violations: list[str] = []
    expected_false = {
        "external_upload_authorized": policy.external_upload_authorized,
        "gpu_training_authorized": policy.gpu_training_authorized,
        "provider_credentials_in_repository": policy.provider_credentials_in_repository,
        "observer_owns_provider_lifetime": policy.observer_owns_provider_lifetime,
    }
    if policy.cpu_validation_allowed is not True:
        violations.append("CPU validation must remain enabled for MLF-004.")
    for field_name, value in expected_false.items():
        if value is not False:
            violations.append(f"{field_name} must remain false in MLF-004.")
    if policy.quota_snapshots_required is not True:
        violations.append("provider quota snapshots must remain required.")
    if policy.artifact_inventory_required is not True:
        violations.append("provider artifact inventory must remain required.")
    if policy.checkpoint_reentry_required is not True:
        violations.append("epoch/checkpoint re-entry receipts must remain required.")
    if policy.reuse_unchanged_provider_capability_evidence is not True:
        violations.append(
            "unchanged provider capability evidence must be reusable instead of re-smoked."
        )
    if policy.inaccessible_status_failures_before_abort != 3:
        violations.append(
            "inaccessible provider status must fail closed after three probes."
        )
    return violations


def build_training_package_entry(
    *,
    role: str,
    name: str,
    content: bytes,
) -> TrainingPackageEntry:
    return TrainingPackageEntry(
        role=role,
        name=name,
        content_fingerprint=fingerprint_bytes(content),
        size_bytes=len(content),
    )


def validate_training_package_manifest(
    manifest: TrainingPackageManifest,
) -> list[str]:
    violations: list[str] = []
    required_text = {
        "package_id": manifest.package_id,
        "dataset_manifest_fingerprint": manifest.dataset_manifest_fingerprint,
        "snapshot_plan_fingerprint": manifest.snapshot_plan_fingerprint,
        "source_snapshot": manifest.source_snapshot,
        "feature_contract_version": manifest.feature_contract_version,
        "product_contract_version": manifest.product_contract_version,
        "code_commit": manifest.code_commit,
    }
    for field_name, value in required_text.items():
        if not value.strip():
            violations.append(f"{field_name} must be non-empty.")

    if manifest.transport_platform != TRANSPORT_PLATFORM:
        violations.append(f"transport_platform must be {TRANSPORT_PLATFORM!r}.")
    if manifest.schema_version != TRAINING_PACKAGE_SCHEMA_VERSION:
        violations.append(
            f"schema_version must be {TRAINING_PACKAGE_SCHEMA_VERSION!r}; "
            f"got {manifest.schema_version!r}."
        )
    for field_name, value in (
        ("dataset_manifest_fingerprint", manifest.dataset_manifest_fingerprint),
        ("snapshot_plan_fingerprint", manifest.snapshot_plan_fingerprint),
    ):
        if value and not _is_sha256_fingerprint(value):
            violations.append(
                f"{field_name} must be a lowercase sha256 fingerprint."
            )

    if not manifest.entries:
        violations.append("training package must contain entries.")
        return violations

    names = [entry.name for entry in manifest.entries]
    if len(names) != len(set(names)):
        violations.append("training package entry names must be unique.")

    role_counts: dict[str, int] = {}
    for entry in manifest.entries:
        role_counts[entry.role] = role_counts.get(entry.role, 0) + 1
        if entry.role not in PACKAGE_ENTRY_ROLES:
            violations.append(
                f"unsupported training package entry role {entry.role!r}."
            )
        if not _is_safe_package_name(entry.name):
            violations.append(
                f"training package entry name {entry.name!r} must be a safe flat filename."
            )
        if not _is_sha256_fingerprint(entry.content_fingerprint):
            violations.append(
                f"training package entry {entry.name!r} must have a lowercase "
                "sha256 fingerprint."
            )
        if entry.size_bytes < 0:
            violations.append(
                f"training package entry {entry.name!r} size_bytes must be non-negative."
            )

    for role in REQUIRED_PACKAGE_ENTRY_ROLES:
        if role_counts.get(role, 0) != 1:
            violations.append(
                f"training package must contain exactly one {role!r} entry."
            )
    return violations


def fingerprint_training_package_manifest(
    manifest: TrainingPackageManifest,
) -> str:
    violations = validate_training_package_manifest(manifest)
    if violations:
        raise ValueError("; ".join(violations))
    return fingerprint_bytes(_canonical_json(asdict(manifest)).encode("utf-8"))


def serialize_training_package_manifest(manifest: TrainingPackageManifest) -> str:
    fingerprint_training_package_manifest(manifest)
    return _canonical_json(asdict(manifest))


def validate_training_package_contents(
    manifest: TrainingPackageManifest,
    contents: Mapping[str, bytes],
) -> CpuValidationReport:
    violations = validate_training_package_manifest(manifest)
    expected_names = {entry.name for entry in manifest.entries}
    actual_names = set(contents)
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    if missing:
        violations.append(f"training package contents missing entries: {missing}.")
    if extra:
        violations.append(
            f"training package contents contain undeclared entries: {extra}."
        )

    entries_by_name = {entry.name: entry for entry in manifest.entries}
    for name in sorted(expected_names & actual_names):
        entry = entries_by_name[name]
        content = contents[name]
        if len(content) != entry.size_bytes:
            violations.append(
                f"training package entry {name!r} size mismatch; "
                f"expected {entry.size_bytes}, got {len(content)}."
            )
        actual_fingerprint = fingerprint_bytes(content)
        if actual_fingerprint != entry.content_fingerprint:
            violations.append(
                f"training package entry {name!r} fingerprint mismatch; "
                f"expected {entry.content_fingerprint!r}, got {actual_fingerprint!r}."
            )
    if violations:
        raise ValueError("; ".join(violations))
    return CpuValidationReport(
        package_fingerprint=fingerprint_training_package_manifest(manifest),
        checked_entries=tuple(sorted(expected_names)),
    )


def assess_compute_intent(intent: ExperimentComputeIntent) -> ComputeAdmission:
    if not intent.experiment_id.strip():
        raise ValueError("experiment_id must be non-empty.")
    if not _is_sha256_fingerprint(intent.training_package_fingerprint):
        raise ValueError(
            "training_package_fingerprint must be a lowercase sha256 fingerprint."
        )
    if intent.compute_class == CPU_VALIDATION_COMPUTE_CLASS:
        if intent.external_execution:
            return ComputeAdmission(
                allowed=False,
                operator_authorization_required=False,
                reason="cpu_validation_must_remain_local_or_ci",
            )
        return ComputeAdmission(
            allowed=True,
            operator_authorization_required=False,
            reason="cpu_validation_allowed",
        )
    if intent.compute_class == GPU_TRAINING_COMPUTE_CLASS:
        return ComputeAdmission(
            allowed=False,
            operator_authorization_required=True,
            reason=(
                "gpu_training_requires_explicit_operator_authorization_"
                "and_future_execution_enablement"
            ),
        )
    raise ValueError(f"unsupported compute_class {intent.compute_class!r}.")


def validate_experiment_artifact_metadata(
    metadata: ExperimentArtifactMetadata,
) -> list[str]:
    violations: list[str] = []
    for field_name, value in {
        "artifact_id": metadata.artifact_id,
        "experiment_id": metadata.experiment_id,
        "code_commit": metadata.code_commit,
        "artifact_kind": metadata.artifact_kind,
    }.items():
        if not value.strip():
            violations.append(f"{field_name} must be non-empty.")
    for field_name, value in (
        ("training_package_fingerprint", metadata.training_package_fingerprint),
        ("content_fingerprint", metadata.content_fingerprint),
    ):
        if not _is_sha256_fingerprint(value):
            violations.append(
                f"{field_name} must be a lowercase sha256 fingerprint."
            )
    if metadata.compute_class not in {
        CPU_VALIDATION_COMPUTE_CLASS,
        GPU_TRAINING_COMPUTE_CLASS,
    }:
        violations.append("artifact compute_class is unsupported.")
    if (
        metadata.compute_class == GPU_TRAINING_COMPUTE_CLASS
        and not metadata.operator_authorization_reference.strip()
    ):
        violations.append(
            "GPU-derived artifacts must retain the explicit operator authorization reference."
        )
    if metadata.product_authority:
        violations.append("experiment artifacts may not claim product authority.")
    return violations


def validate_telemetry_event(event: ExperimentTelemetryEvent) -> list[str]:
    violations: list[str] = []
    if not event.experiment_id.strip():
        violations.append("experiment_id must be non-empty.")
    if not _is_sha256_fingerprint(event.training_package_fingerprint):
        violations.append(
            "training_package_fingerprint must be a lowercase sha256 fingerprint."
        )
    if event.event_type not in TELEMETRY_EVENT_TYPES:
        violations.append(f"unsupported telemetry event_type {event.event_type!r}.")
    if not _is_utc_timestamp(event.observed_at_utc):
        violations.append("observed_at_utc must use UTC offset/Z semantics.")
    if event.compute_class not in {
        CPU_VALIDATION_COMPUTE_CLASS,
        GPU_TRAINING_COMPUTE_CLASS,
    }:
        violations.append("telemetry compute_class is unsupported.")
    if event.epoch is not None and event.epoch <= 0:
        violations.append("telemetry epoch must be positive when present.")
    if event.details_fingerprint and not _is_sha256_fingerprint(
        event.details_fingerprint
    ):
        violations.append(
            "details_fingerprint must be a lowercase sha256 fingerprint when present."
        )
    if event.product_authority:
        violations.append("telemetry may not claim product authority.")
    return violations


def validate_epoch_reentry_checkpoint(
    checkpoint: EpochReentryCheckpoint,
) -> list[str]:
    violations: list[str] = []
    if not checkpoint.experiment_id.strip():
        violations.append("experiment_id must be non-empty.")
    if checkpoint.epoch_completed <= 0:
        violations.append("epoch_completed must be positive.")
    if checkpoint.state not in CHECKPOINT_STATES:
        violations.append(f"unsupported checkpoint state {checkpoint.state!r}.")
    for field_name, value in (
        ("training_package_fingerprint", checkpoint.training_package_fingerprint),
        (
            "checkpoint_artifact_fingerprint",
            checkpoint.checkpoint_artifact_fingerprint,
        ),
        ("metrics_fingerprint", checkpoint.metrics_fingerprint),
    ):
        if not _is_sha256_fingerprint(value):
            violations.append(
                f"{field_name} must be a lowercase sha256 fingerprint."
            )
    if checkpoint.resume_parent_fingerprint and not _is_sha256_fingerprint(
        checkpoint.resume_parent_fingerprint
    ):
        violations.append(
            "resume_parent_fingerprint must be a lowercase sha256 fingerprint when present."
        )
    if not checkpoint.code_commit.strip():
        violations.append("code_commit must be non-empty.")
    if not checkpoint.provider_run_reference.strip():
        violations.append("provider_run_reference must be non-empty.")
    if not checkpoint.operator_authorization_reference.strip():
        violations.append(
            "GPU checkpoint must retain the explicit operator authorization reference."
        )
    if checkpoint.product_authority:
        violations.append("epoch re-entry checkpoints may not claim product authority.")
    return violations


def fingerprint_epoch_reentry_checkpoint(
    checkpoint: EpochReentryCheckpoint,
) -> str:
    violations = validate_epoch_reentry_checkpoint(checkpoint)
    if violations:
        raise ValueError("; ".join(violations))
    return fingerprint_bytes(_canonical_json(asdict(checkpoint)).encode("utf-8"))


def validate_resume_chain(
    previous: EpochReentryCheckpoint,
    current: EpochReentryCheckpoint,
) -> list[str]:
    violations = [
        *validate_epoch_reentry_checkpoint(previous),
        *validate_epoch_reentry_checkpoint(current),
    ]
    if violations:
        return violations
    if current.experiment_id != previous.experiment_id:
        violations.append("resume chain experiment_id changed.")
    if current.training_package_fingerprint != previous.training_package_fingerprint:
        violations.append("resume chain training package changed.")
    if current.operator_authorization_reference != previous.operator_authorization_reference:
        violations.append("resume chain operator authorization changed.")
    if current.epoch_completed <= previous.epoch_completed:
        violations.append("resume chain epoch must advance.")
    expected_parent = fingerprint_epoch_reentry_checkpoint(previous)
    if current.resume_parent_fingerprint != expected_parent:
        violations.append("resume chain parent fingerprint mismatch.")
    return violations


def fingerprint_diagnostic_receipt(receipt: DiagnosticReceipt) -> str:
    if (
        not receipt.experiment_id.strip()
        or not receipt.stage.strip()
        or not receipt.evidence_key.strip()
    ):
        raise ValueError("diagnostic identity fields must be non-empty.")
    if receipt.failure_class not in DIAGNOSTIC_CLASSES:
        raise ValueError(
            f"unsupported diagnostic failure_class {receipt.failure_class!r}."
        )
    if not _is_sha256_fingerprint(receipt.details_fingerprint):
        raise ValueError(
            "details_fingerprint must be a lowercase sha256 fingerprint."
        )
    if receipt.product_authority:
        raise ValueError("diagnostics may not claim product authority.")
    return fingerprint_bytes(_canonical_json(asdict(receipt)).encode("utf-8"))
