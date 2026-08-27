from __future__ import annotations

import pytest

from src.connectors.base import RawJobRecord
from src.ingestion.complete_inventory_lifecycle import (
    COMPLETE_INVENTORY_OBSERVER,
    plan_verified_complete_inventory_absences,
    reconcile_verified_complete_inventory_health,
    verified_complete_inventory_authority,
)
from src.job_lifecycle_health import (
    COVERAGE_COMPLETE_INVENTORY,
    OUTCOME_NOT_SEEN,
    JobHealthTarget,
)
from src.search_intelligence.personio_target_authority import (
    PERSONIO_TARGET_AUTHORITY_VERSION,
)


SOURCE = "personio:eraneos"
TARGET_KEY = "eraneos"
FEED_URL = "https://eraneos.jobs.personio.de/xml?language=de"
AUTHORITY_FINGERPRINT = "feed-fingerprint-001"


def record(
    external_job_id: str | None,
    *,
    position_count: int,
    fingerprint: str = AUTHORITY_FINGERPRINT,
    source_name: str = SOURCE,
    target_key: str = TARGET_KEY,
    product_authority: bool = False,
    source_url: str | None = None,
) -> RawJobRecord:
    if source_url is None:
        source_url = (
            f"https://{target_key}.jobs.personio.de/job/{external_job_id}"
            "?language=de"
            if external_job_id
            else FEED_URL
        )

    return RawJobRecord(
        source_name=source_name,
        source_url=source_url,
        external_job_id=external_job_id,
        raw_data={
            "source_type": "employer_origin_ats_backed_career_site",
            "source_target": {
                "source_family": "personio",
                "target_key": target_key,
                "host": f"{target_key}.jobs.personio.de",
                "language": "de",
            },
            "job": {
                "source_url": source_url,
                "title": "Example role",
            },
            "ats_feed_authority": {
                "contract_version": (
                    "personio-recurring-feed-authority.v1"
                ),
                "reviewed_binding_contract": (
                    "runtime_203_personio_target_authority_shadow_v1"
                ),
                "validator_contract_version": (
                    PERSONIO_TARGET_AUTHORITY_VERSION
                ),
                "provider": "personio",
                "target_key": target_key,
                "authority_validated": True,
                "employer_identity_bound": True,
                "feed_inventory_complete": True,
                "http_status_code": 200,
                "requested_url": FEED_URL,
                "final_url": FEED_URL,
                "matched_company_name": (
                    "Eraneos Analytics Germany GmbH"
                ),
                "matched_employer_alias": "Eraneos",
                "position_count": position_count,
                "reason_codes": [],
                "evidence_fingerprint": fingerprint,
                "product_authority": product_authority,
            },
        },
    )


def target(
    silver_job_id: int,
    external_job_id: str | None,
    *,
    source_url: str,
    canonical_source_type: str | None = (
        "employer_origin_ats_backed_career_site"
    ),
    raw_source_type: str | None = (
        "employer_origin_ats_backed_career_site"
    ),
) -> JobHealthTarget:
    return JobHealthTarget(
        silver_job_id=silver_job_id,
        raw_job_id=1000 + silver_job_id,
        ingestion_run_id=2000 + silver_job_id,
        source_name=SOURCE,
        external_job_id=external_job_id,
        source_url=source_url,
        title="Example role",
        canonical_source_type=canonical_source_type,
        raw_source_type=raw_source_type,
    )


class FakeHealthRepository:
    def __init__(self, targets: list[JobHealthTarget]) -> None:
        self.targets = targets
        self.load_calls = 0
        self.batch_calls = 0
        self.batch_payload = None

    def load_active_targets_for_verified_complete_inventory_source(
        self,
        source_name: str,
    ) -> list[JobHealthTarget]:
        self.load_calls += 1
        assert source_name == SOURCE
        return list(self.targets)

    def append_complete_inventory_absence_batch(
        self,
        *,
        expected_classifications,
        expected_source_name: str,
        observed_by: str,
        ingestion_run_id: int,
    ) -> list[int]:
        self.batch_calls += 1
        self.batch_payload = (
            list(expected_classifications),
            expected_source_name,
            observed_by,
            ingestion_run_id,
        )
        return [
            9000 + index
            for index, _ in enumerate(
                expected_classifications,
                start=1,
            )
        ]


def test_valid_reviewed_personio_inventory_has_authority() -> None:
    records = [
        record("2001", position_count=2),
        record("2002", position_count=2),
    ]

    authority = verified_complete_inventory_authority(
        source_name=SOURCE,
        records=records,
    )

    assert authority is not None
    assert authority.provider == "personio"
    assert authority.target_key == TARGET_KEY
    assert authority.position_count == 2
    assert authority.evidence_fingerprint == AUTHORITY_FINGERPRINT


def test_empty_inventory_has_no_complete_inventory_authority() -> None:
    assert (
        verified_complete_inventory_authority(
            source_name=SOURCE,
            records=[],
        )
        is None
    )


def test_unreviewed_personio_target_has_no_authority() -> None:
    other_source = "personio:not-reviewed"

    assert (
        verified_complete_inventory_authority(
            source_name=other_source,
            records=[
                record(
                    "1",
                    position_count=1,
                    source_name=other_source,
                    target_key="not-reviewed",
                )
            ],
        )
        is None
    )


def test_mixed_authority_fingerprints_fail_closed() -> None:
    records = [
        record("2001", position_count=2, fingerprint="a"),
        record("2002", position_count=2, fingerprint="b"),
    ]

    assert (
        verified_complete_inventory_authority(
            source_name=SOURCE,
            records=records,
        )
        is None
    )


def test_position_count_must_equal_current_full_inventory() -> None:
    records = [
        record("2001", position_count=3),
        record("2002", position_count=3),
    ]

    assert (
        verified_complete_inventory_authority(
            source_name=SOURCE,
            records=records,
        )
        is None
    )


def test_product_authority_flag_must_remain_false() -> None:
    assert (
        verified_complete_inventory_authority(
            source_name=SOURCE,
            records=[
                record(
                    "2001",
                    position_count=1,
                    product_authority=True,
                )
            ],
        )
        is None
    )


def test_inventory_record_requires_source_local_identity() -> None:
    assert (
        verified_complete_inventory_authority(
            source_name=SOURCE,
            records=[
                record(
                    None,
                    position_count=1,
                    source_url=FEED_URL,
                )
            ],
        )
        is None
    )


def test_plan_matches_id_and_exact_url_fallback() -> None:
    records = [
        record("2001", position_count=2),
        record("2002", position_count=2),
    ]
    authority = verified_complete_inventory_authority(
        source_name=SOURCE,
        records=records,
    )
    assert authority is not None

    targets = [
        target(
            1,
            "2001",
            source_url=(
                "https://eraneos.jobs.personio.de/job/2001"
                "?language=de"
            ),
        ),
        target(
            2,
            "provider-id-drifted",
            source_url=(
                "https://eraneos.jobs.personio.de/job/2002"
                "?language=de"
            ),
        ),
        target(
            3,
            "2003",
            source_url=(
                "https://eraneos.jobs.personio.de/job/2003"
                "?language=de"
            ),
        ),
    ]

    plan = plan_verified_complete_inventory_absences(
        source_name=SOURCE,
        authority=authority,
        records=records,
        targets=targets,
    )

    assert plan is not None
    assert plan.observed_target_ids == (1, 2)
    assert [item.silver_job_id for item in plan.missing_targets] == [3]


def test_reconcile_writes_exactly_one_not_seen_complete_inventory() -> None:
    records = [
        record("2001", position_count=1),
    ]

    repository = FakeHealthRepository(
        [
            target(
                1,
                "2001",
                source_url=(
                    "https://eraneos.jobs.personio.de/job/2001"
                    "?language=de"
                ),
            ),
            target(
                2,
                "2002",
                source_url=(
                    "https://eraneos.jobs.personio.de/job/2002"
                    "?language=de"
                ),
            ),
        ]
    )

    summary = reconcile_verified_complete_inventory_health(
        health_repository=repository,
        source_name=SOURCE,
        observed_records=records,
        ingestion_run_id=77,
    )

    assert summary is not None
    assert summary.target_count == 2
    assert summary.observed_target_count == 1
    assert summary.missing_target_count == 1
    assert summary.not_seen_write_count == 1

    assert repository.batch_calls == 1
    assert repository.batch_payload is not None

    (
        payload,
        expected_source_name,
        observed_by,
        ingestion_run_id,
    ) = repository.batch_payload

    assert expected_source_name == SOURCE
    assert observed_by == COMPLETE_INVENTORY_OBSERVER
    assert ingestion_run_id == 77
    assert len(payload) == 1

    missing_target, classification = payload[0]
    assert missing_target.silver_job_id == 2
    assert classification.outcome == OUTCOME_NOT_SEEN
    assert classification.coverage == COVERAGE_COMPLETE_INVENTORY
    assert (
        classification.evidence_reason
        == "authoritative_verified_ats_complete_inventory_absence"
    )
    assert classification.evidence["product_authority"] is False
    assert classification.evidence["raw_inventory_persisted"] is False


def test_invalid_authority_falls_back_without_loading_targets() -> None:
    repository = FakeHealthRepository([])

    result = reconcile_verified_complete_inventory_health(
        health_repository=repository,
        source_name=SOURCE,
        observed_records=[],
        ingestion_run_id=78,
    )

    assert result is None
    assert repository.load_calls == 0
    assert repository.batch_calls == 0


def test_bulk_absence_fails_before_batch_write() -> None:
    repository = FakeHealthRepository(
        [
            target(
                index,
                f"missing-{index}",
                source_url=(
                    "https://eraneos.jobs.personio.de/job/"
                    f"missing-{index}?language=de"
                ),
            )
            for index in (1, 2, 3)
        ]
    )

    with pytest.raises(
        RuntimeError,
        match="absence exceeds bounded write cap",
    ):
        reconcile_verified_complete_inventory_health(
            health_repository=repository,
            source_name=SOURCE,
            observed_records=[
                record("2001", position_count=1)
            ],
            ingestion_run_id=79,
            max_absences=2,
        )

    assert repository.batch_calls == 0



def test_current_verified_inventory_can_close_legacy_target_without_rewritten_bronze_type(
) -> None:
    records = [
        record("2001", position_count=1),
    ]

    repository = FakeHealthRepository(
        [
            target(
                1,
                "2001",
                source_url=(
                    "https://eraneos.jobs.personio.de/job/2001"
                    "?language=de"
                ),
            ),
            target(
                2,
                "legacy-2002",
                source_url=(
                    "https://eraneos.jobs.personio.de/job/legacy-2002"
                    "?language=de"
                ),
                canonical_source_type=None,
                raw_source_type=None,
            ),
        ]
    )

    summary = reconcile_verified_complete_inventory_health(
        health_repository=repository,
        source_name=SOURCE,
        observed_records=records,
        ingestion_run_id=80,
    )

    assert summary is not None
    assert summary.missing_target_count == 1
    assert summary.not_seen_write_count == 1

    assert repository.batch_payload is not None
    payload = repository.batch_payload[0]

    missing_target, classification = payload[0]

    assert missing_target.silver_job_id == 2
    assert missing_target.canonical_source_type is None
    assert missing_target.raw_source_type is None
    assert classification.outcome == OUTCOME_NOT_SEEN
    assert classification.coverage == COVERAGE_COMPLETE_INVENTORY
