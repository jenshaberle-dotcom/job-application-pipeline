from __future__ import annotations

from dataclasses import replace

import pytest

from src.search_intelligence.ml_experiment_transport import (
    CPU_VALIDATION_COMPUTE_CLASS,
    GPU_TRAINING_COMPUTE_CLASS,
    DiagnosticReceipt,
    EpochReentryCheckpoint,
    ExperimentArtifactMetadata,
    ExperimentComputeIntent,
    ExperimentTelemetryEvent,
    KaggleTransportPolicy,
    TrainingPackageManifest,
    assess_compute_intent,
    build_training_package_entry,
    fingerprint_bytes,
    fingerprint_diagnostic_receipt,
    fingerprint_epoch_reentry_checkpoint,
    fingerprint_training_package_manifest,
    serialize_training_package_manifest,
    validate_epoch_reentry_checkpoint,
    validate_experiment_artifact_metadata,
    validate_kaggle_transport_policy,
    validate_resume_chain,
    validate_telemetry_event,
    validate_training_package_contents,
    validate_training_package_manifest,
)


def _fingerprint(seed: str) -> str:
    return fingerprint_bytes(seed.encode("utf-8"))


def _package() -> tuple[TrainingPackageManifest, dict[str, bytes]]:
    contents = {
        "dataset.parquet": b"deterministic-dataset-payload",
        "dataset-manifest.json": b'{"schema_version":"dataset-v1"}',
        "snapshot.json": b'{"source_snapshot":"snapshot-001"}',
    }
    entries = (
        build_training_package_entry(
            role="dataset_payload",
            name="dataset.parquet",
            content=contents["dataset.parquet"],
        ),
        build_training_package_entry(
            role="dataset_manifest",
            name="dataset-manifest.json",
            content=contents["dataset-manifest.json"],
        ),
        build_training_package_entry(
            role="snapshot_metadata",
            name="snapshot.json",
            content=contents["snapshot.json"],
        ),
    )
    manifest = TrainingPackageManifest(
        package_id="mlf004-package-001",
        dataset_manifest_fingerprint=_fingerprint("dataset-manifest"),
        snapshot_plan_fingerprint=_fingerprint("snapshot-plan"),
        source_snapshot="silver-snapshot-001",
        feature_contract_version="job-features/v1",
        product_contract_version="product-v1",
        code_commit="f7f6d6c1d53d11be4235d96243b2cc5a0cb9271e",
        entries=entries,
    )
    return manifest, contents


def _checkpoint(
    *,
    epoch: int,
    parent: str = "",
    experiment_id: str = "experiment-001",
    package_fingerprint: str | None = None,
    authorization: str = "operator-auth-001",
) -> EpochReentryCheckpoint:
    package, _ = _package()
    return EpochReentryCheckpoint(
        experiment_id=experiment_id,
        training_package_fingerprint=(
            package_fingerprint or fingerprint_training_package_manifest(package)
        ),
        epoch_completed=epoch,
        checkpoint_artifact_fingerprint=_fingerprint(f"checkpoint-{epoch}"),
        metrics_fingerprint=_fingerprint(f"metrics-{epoch}"),
        code_commit="future-authorized-training-head",
        provider_run_reference="kaggle:future-run-001",
        operator_authorization_reference=authorization,
        resume_parent_fingerprint=parent,
    )


def test_default_transport_policy_allows_cpu_but_not_external_or_gpu() -> None:
    policy = KaggleTransportPolicy()

    assert validate_kaggle_transport_policy(policy) == []
    assert policy.cpu_validation_allowed is True
    assert policy.external_upload_authorized is False
    assert policy.gpu_training_authorized is False
    assert policy.provider_credentials_in_repository is False
    assert policy.observer_owns_provider_lifetime is False
    assert policy.reuse_unchanged_provider_capability_evidence is True


def test_transport_policy_fails_closed_on_governance_drift() -> None:
    invalid = KaggleTransportPolicy(
        external_upload_authorized=True,
        gpu_training_authorized=True,
        provider_credentials_in_repository=True,
        observer_owns_provider_lifetime=True,
        quota_snapshots_required=False,
        artifact_inventory_required=False,
        checkpoint_reentry_required=False,
        reuse_unchanged_provider_capability_evidence=False,
        inaccessible_status_failures_before_abort=4,
    )

    violations = validate_kaggle_transport_policy(invalid)

    assert any("external_upload_authorized" in item for item in violations)
    assert any("gpu_training_authorized" in item for item in violations)
    assert any("provider_credentials_in_repository" in item for item in violations)
    assert any("observer_owns_provider_lifetime" in item for item in violations)
    assert any("quota snapshots" in item for item in violations)
    assert any("artifact inventory" in item for item in violations)
    assert any("re-entry" in item for item in violations)
    assert any("re-smoked" in item for item in violations)
    assert any("three probes" in item for item in violations)


def test_cpu_validation_checks_exact_package_bytes_and_is_deterministic() -> None:
    manifest, contents = _package()

    report = validate_training_package_contents(manifest, contents)

    assert report.compute_class == CPU_VALIDATION_COMPUTE_CLASS
    assert report.external_execution is False
    assert report.product_authority is False
    assert report.checked_entries == (
        "dataset-manifest.json",
        "dataset.parquet",
        "snapshot.json",
    )
    assert report.package_fingerprint == fingerprint_training_package_manifest(manifest)
    assert fingerprint_training_package_manifest(manifest) == (
        fingerprint_training_package_manifest(manifest)
    )
    assert serialize_training_package_manifest(manifest) == (
        serialize_training_package_manifest(manifest)
    )


def test_cpu_validation_rejects_missing_extra_or_tampered_package_content() -> None:
    manifest, contents = _package()
    tampered = {
        **contents,
        "dataset.parquet": b"tampered",
        "undeclared.bin": b"extra",
    }
    tampered.pop("snapshot.json")

    with pytest.raises(ValueError) as excinfo:
        validate_training_package_contents(manifest, tampered)

    message = str(excinfo.value)
    assert "missing entries" in message
    assert "undeclared entries" in message
    assert "size mismatch" in message
    assert "fingerprint mismatch" in message


def test_training_package_rejects_path_escape_or_duplicate_required_role() -> None:
    manifest, _ = _package()
    unsafe = replace(
        manifest.entries[0],
        name="../dataset.parquet",
    )
    duplicate_role = replace(
        manifest.entries[2],
        role="dataset_payload",
    )
    invalid = replace(
        manifest,
        entries=(unsafe, manifest.entries[1], duplicate_role),
    )

    violations = validate_training_package_manifest(invalid)

    assert any("safe flat filename" in item for item in violations)
    assert any("exactly one 'dataset_payload'" in item for item in violations)


def test_local_cpu_compute_is_admitted_but_external_cpu_is_not() -> None:
    package, _ = _package()
    package_fingerprint = fingerprint_training_package_manifest(package)
    local = ExperimentComputeIntent(
        experiment_id="cpu-validation-001",
        training_package_fingerprint=package_fingerprint,
        compute_class=CPU_VALIDATION_COMPUTE_CLASS,
        external_execution=False,
    )
    external = replace(local, external_execution=True)

    local_decision = assess_compute_intent(local)
    external_decision = assess_compute_intent(external)

    assert local_decision.allowed is True
    assert local_decision.operator_authorization_required is False
    assert external_decision.allowed is False
    assert external_decision.operator_authorization_required is False


def test_gpu_compute_is_always_blocked_in_mlf004_even_with_authorization_reference() -> None:
    package, _ = _package()
    intent = ExperimentComputeIntent(
        experiment_id="gpu-training-future",
        training_package_fingerprint=fingerprint_training_package_manifest(package),
        compute_class=GPU_TRAINING_COMPUTE_CLASS,
        external_execution=True,
        operator_authorization_reference="operator-auth-present-but-no-execution-slice",
    )

    decision = assess_compute_intent(intent)

    assert decision.allowed is False
    assert decision.operator_authorization_required is True
    assert "future_execution_enablement" in decision.reason


def test_gpu_artifact_metadata_requires_authorization_provenance() -> None:
    package, _ = _package()
    metadata = ExperimentArtifactMetadata(
        artifact_id="artifact-001",
        experiment_id="experiment-001",
        training_package_fingerprint=fingerprint_training_package_manifest(package),
        artifact_kind="checkpoint",
        content_fingerprint=_fingerprint("artifact"),
        code_commit="future-training-head",
        compute_class=GPU_TRAINING_COMPUTE_CLASS,
    )

    violations = validate_experiment_artifact_metadata(metadata)

    assert any("operator authorization" in item for item in violations)
    assert validate_experiment_artifact_metadata(
        replace(metadata, operator_authorization_reference="operator-auth-001")
    ) == []


def test_telemetry_contract_accepts_utc_epoch_event_and_rejects_non_utc() -> None:
    package, _ = _package()
    event = ExperimentTelemetryEvent(
        experiment_id="experiment-001",
        training_package_fingerprint=fingerprint_training_package_manifest(package),
        event_type="epoch_checkpoint",
        observed_at_utc="2026-08-23T15:30:00Z",
        compute_class=GPU_TRAINING_COMPUTE_CLASS,
        provider_run_reference="kaggle:future-run-001",
        epoch=5,
        details_fingerprint=_fingerprint("epoch-5-telemetry"),
    )

    assert validate_telemetry_event(event) == []
    violations = validate_telemetry_event(
        replace(event, observed_at_utc="2026-08-23T17:30:00+02:00")
    )
    assert "observed_at_utc must use UTC offset/Z semantics." in violations


def test_epoch_checkpoint_is_self_identifying_and_resume_chain_is_verified() -> None:
    previous = _checkpoint(epoch=5)
    previous_fingerprint = fingerprint_epoch_reentry_checkpoint(previous)
    current = _checkpoint(epoch=10, parent=previous_fingerprint)

    assert validate_epoch_reentry_checkpoint(previous) == []
    assert validate_epoch_reentry_checkpoint(current) == []
    assert previous_fingerprint.startswith("sha256:")
    assert validate_resume_chain(previous, current) == []


def test_resume_chain_rejects_changed_package_auth_or_nonadvancing_epoch() -> None:
    previous = _checkpoint(epoch=5)
    previous_fingerprint = fingerprint_epoch_reentry_checkpoint(previous)
    current = _checkpoint(
        epoch=5,
        parent=previous_fingerprint,
        package_fingerprint=_fingerprint("different-package"),
        authorization="different-authorization",
    )

    violations = validate_resume_chain(previous, current)

    assert "resume chain training package changed." in violations
    assert "resume chain operator authorization changed." in violations
    assert "resume chain epoch must advance." in violations


def test_diagnostic_receipt_has_stable_failure_fingerprint() -> None:
    receipt = DiagnosticReceipt(
        experiment_id="experiment-001",
        stage="provider_observation",
        failure_class="operational_failure",
        evidence_key="provider-status-inaccessible",
        details_fingerprint=_fingerprint("status-log"),
        provider_run_reference="kaggle:future-run-001",
    )

    first = fingerprint_diagnostic_receipt(receipt)
    second = fingerprint_diagnostic_receipt(receipt)

    assert first == second
    assert first.startswith("sha256:")
    with pytest.raises(ValueError, match="unsupported diagnostic failure_class"):
        fingerprint_diagnostic_receipt(
            replace(receipt, failure_class="retry_until_green")
        )
