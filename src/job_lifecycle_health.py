from __future__ import annotations

from collections.abc import Sequence

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import psycopg
import requests
from psycopg.rows import dict_row

from src.config import get_database_config
from src.search_intelligence.vacancy_page_signals import (
    explicit_vacancy_closure_marker,
)


APPROVAL_TOKEN = "JOB-LIFECYCLE-HEALTH-001"
COVERAGE_EXACT_DETAIL = "exact_detail"
COVERAGE_COMPLETE_INVENTORY = "complete_inventory"
OUTCOME_SEEN_ACTIVE = "seen_active"
OUTCOME_NOT_SEEN = "not_seen"
OUTCOME_CLOSED = "closed"
OUTCOME_UNVERIFIABLE = "unverifiable"
REQUEST_TIMEOUT_SECONDS = 15.0
MAX_CLASSIFICATION_BODY_CHARS = 1_000_000
EMPLOYER_ORIGIN_HEALTH_SOURCE_TYPES = frozenset(
    {
        "employer_origin_career_site",
        "employer_origin_ats_backed_career_site",
    }
)
USER_AGENT = (
    "job-application-pipeline-vacancy-health/0.1 "
    "(bounded exact-detail lifecycle probe)"
)


@dataclass(frozen=True)
class JobHealthTarget:
    silver_job_id: int
    raw_job_id: int
    ingestion_run_id: int | None
    source_name: str
    external_job_id: str | None
    source_url: str
    title: str
    canonical_source_type: str | None
    raw_source_type: str | None


@dataclass(frozen=True)
class HttpProbeResult:
    status_code: int | None
    final_url: str
    response_text: str
    redirect_count: int
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class HealthClassification:
    outcome: str
    coverage: str
    evidence_reason: str
    evidence: dict[str, object]


class JobLifecycleHealthRepository:
    def __init__(self) -> None:
        self.connection_config = get_database_config()

    def get_connection(self):
        return psycopg.connect(
            **self.connection_config,
            row_factory=dict_row,
        )

    @staticmethod
    def _target_from_row(row: dict) -> JobHealthTarget:
        return JobHealthTarget(
            silver_job_id=int(row["silver_job_id"]),
            raw_job_id=int(row["raw_job_id"]),
            ingestion_run_id=row["ingestion_run_id"],
            source_name=str(row["source_name"]),
            external_job_id=row["external_job_id"],
            source_url=str(row["source_url"]),
            title=str(row["title"] or ""),
            canonical_source_type=row["canonical_source_type"],
            raw_source_type=row["raw_source_type"],
        )

    @staticmethod
    def _target_query(*, for_update: bool) -> str:
        lock = " FOR UPDATE OF sj, r" if for_update else ""
        return (
            "SELECT "
            "sj.id AS silver_job_id, sj.raw_job_id, "
            "r.ingestion_run_id, sj.source_name, sj.external_job_id, "
            "sj.source_url, sj.title, sj.canonical_source_type, "
            "r.raw_data->>'source_type' AS raw_source_type "
            "FROM silver_jobs sj "
            "JOIN raw_jobs r ON r.id = sj.raw_job_id "
            "WHERE sj.id = %s" + lock
        )

    def load_target(self, silver_job_id: int) -> JobHealthTarget:
        if silver_job_id <= 0:
            raise ValueError("silver_job_id must be a positive integer")

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self._target_query(for_update=False),
                    (silver_job_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise ValueError(f"Silver job not found: {silver_job_id}")

        return self._target_from_row(row)

    def load_active_targets_for_source(
        self,
        source_name: str,
    ) -> list[JobHealthTarget]:
        """Load current employer-origin exact-detail targets for recurring recheck."""

        if not source_name.strip():
            raise ValueError("source_name must not be empty")

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        sj.id AS silver_job_id,
                        sj.raw_job_id,
                        r.ingestion_run_id,
                        sj.source_name,
                        sj.external_job_id,
                        sj.source_url,
                        sj.title,
                        sj.canonical_source_type,
                        r.raw_data->>'source_type' AS raw_source_type
                    FROM gold_job_lifecycle_health lifecycle
                    JOIN silver_jobs sj
                      ON sj.id = lifecycle.silver_job_id
                    JOIN raw_jobs r
                      ON r.id = sj.raw_job_id
                    WHERE sj.source_name = %s
                      AND lifecycle.lifecycle_status = 'active_confirmed'
                      AND NULLIF(btrim(sj.source_url), '') IS NOT NULL
                      AND (
                            sj.canonical_source_type IN (
                                'employer_origin_career_site',
                                'employer_origin_ats_backed_career_site'
                            )
                            OR r.raw_data->>'source_type' IN (
                                'employer_origin_career_site',
                                'employer_origin_ats_backed_career_site'
                            )
                      )
                    ORDER BY
                        lifecycle.last_health_checked_at NULLS FIRST,
                        sj.id
                    """,
                    (source_name.strip(),),
                )
                rows = cur.fetchall()

        return [self._target_from_row(row) for row in rows]

    def load_active_targets_for_verified_complete_inventory_source(
        self,
        source_name: str,
    ) -> list[JobHealthTarget]:
        """Load current targets after source-level inventory authority is proven.

        Unlike the exact-detail loader, this path intentionally does not require
        historical Bronze/Silver source-type projection. Migration 099 proves
        reviewed recurring ATS authority from current job-observation evidence
        without rewriting legacy Bronze rows.

        This method itself grants no authority. Callers must first prove the
        current complete-inventory source contract.
        """

        if not source_name.strip():
            raise ValueError("source_name must not be empty")

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        sj.id AS silver_job_id,
                        sj.raw_job_id,
                        r.ingestion_run_id,
                        sj.source_name,
                        sj.external_job_id,
                        sj.source_url,
                        sj.title,
                        sj.canonical_source_type,
                        r.raw_data->>'source_type' AS raw_source_type
                    FROM gold_job_lifecycle_health lifecycle
                    JOIN silver_jobs sj
                      ON sj.id = lifecycle.silver_job_id
                    JOIN raw_jobs r
                      ON r.id = sj.raw_job_id
                    WHERE sj.source_name = %s
                      AND lifecycle.lifecycle_status = 'active_confirmed'
                      AND NULLIF(btrim(sj.source_url), '') IS NOT NULL
                    ORDER BY
                        lifecycle.last_health_checked_at NULLS FIRST,
                        sj.id
                    """,
                    (source_name.strip(),),
                )
                rows = cur.fetchall()

        return [self._target_from_row(row) for row in rows]

    def append_health_observation(
        self,
        *,
        expected_target: JobHealthTarget,
        classification: HealthClassification,
        observed_by: str,
        ingestion_run_id: int | None = None,
    ) -> int:
        if not observed_by.strip():
            raise ValueError("observed_by must not be empty")

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    self._target_query(for_update=True),
                    (expected_target.silver_job_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise ValueError(
                        f"Silver job disappeared before apply: "
                        f"{expected_target.silver_job_id}"
                    )

                current_target = self._target_from_row(row)
                ensure_expected_target(
                    current_target,
                    expected_source_name=expected_target.source_name,
                    expected_source_url=expected_target.source_url,
                )
                if current_target != expected_target:
                    raise ValueError(
                        "Target identity drifted between probe and apply"
                    )

                cur.execute(
                    "INSERT INTO job_health_observations ("
                    "raw_job_id, ingestion_run_id, source_name, "
                    "external_job_id, source_url, outcome, coverage, "
                    "evidence_reason, evidence, observed_by"
                    ") VALUES ("
                    "%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s"
                    ") RETURNING id",
                    (
                        current_target.raw_job_id,
                        (
                            ingestion_run_id
                            if ingestion_run_id is not None
                            else current_target.ingestion_run_id
                        ),
                        current_target.source_name,
                        current_target.external_job_id,
                        current_target.source_url,
                        classification.outcome,
                        classification.coverage,
                        classification.evidence_reason,
                        json.dumps(
                            classification.evidence,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        observed_by.strip(),
                    ),
                )
                observation_id = int(cur.fetchone()["id"])

            conn.commit()

        return observation_id


    def append_complete_inventory_absence_batch(
        self,
        *,
        expected_classifications: Sequence[
            tuple[JobHealthTarget, HealthClassification]
        ],
        expected_source_name: str,
        observed_by: str,
        ingestion_run_id: int,
    ) -> list[int]:
        """Atomically append verified complete-inventory absence evidence."""

        expected_source_name = expected_source_name.strip()
        if not expected_source_name:
            raise ValueError("expected_source_name must not be empty")
        if not observed_by.strip():
            raise ValueError("observed_by must not be empty")
        if ingestion_run_id <= 0:
            raise ValueError("ingestion_run_id must be positive")
        if not expected_classifications:
            return []

        for target, classification in expected_classifications:
            if target.source_name != expected_source_name:
                raise ValueError(
                    "complete-inventory batch contains another source"
                )
            if (
                classification.outcome != OUTCOME_NOT_SEEN
                or classification.coverage
                != COVERAGE_COMPLETE_INVENTORY
            ):
                raise ValueError(
                    "complete-inventory batch only accepts "
                    "not_seen/complete_inventory"
                )

        target_ids = [
            target.silver_job_id
            for target, _ in expected_classifications
        ]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError(
                "health observation batch contains duplicate Silver targets"
            )

        observation_ids: list[int] = []

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                for expected_target, classification in expected_classifications:
                    cur.execute(
                        self._target_query(for_update=True),
                        (expected_target.silver_job_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise ValueError(
                            "Silver job disappeared before batch apply: "
                            f"{expected_target.silver_job_id}"
                        )

                    current_target = self._target_from_row(row)
                    ensure_expected_target_identity(
                        current_target,
                        expected_source_name=expected_source_name,
                        expected_source_url=expected_target.source_url,
                    )
                    if current_target != expected_target:
                        raise ValueError(
                            "Target identity drifted before batch apply"
                        )

                    cur.execute(
                        "INSERT INTO job_health_observations ("
                        "raw_job_id, ingestion_run_id, source_name, "
                        "external_job_id, source_url, outcome, coverage, "
                        "evidence_reason, evidence, observed_by"
                        ") VALUES ("
                        "%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s"
                        ") RETURNING id",
                        (
                            current_target.raw_job_id,
                            ingestion_run_id,
                            current_target.source_name,
                            current_target.external_job_id,
                            current_target.source_url,
                            classification.outcome,
                            classification.coverage,
                            classification.evidence_reason,
                            json.dumps(
                                classification.evidence,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                            observed_by.strip(),
                        ),
                    )
                    inserted = cur.fetchone()
                    if inserted is None:
                        raise RuntimeError(
                            "health observation batch insert returned no id"
                        )
                    observation_ids.append(int(inserted["id"]))

            conn.commit()

        return observation_ids


def normalize_url_identity(value: str) -> str:
    parsed = urlsplit(value.strip())
    scheme = parsed.scheme.casefold()
    netloc = parsed.netloc.casefold()
    path = unquote(parsed.path).rstrip("/") or "/"
    query_pairs = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    query = urlencode(query_pairs, doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    collapsed = re.sub(r"[^0-9a-z]+", " ", without_marks.casefold())
    return re.sub(r"\s+", " ", collapsed).strip()


def title_is_confirmed(expected_title: str, response_text: str) -> bool:
    normalized_title = normalize_text(expected_title)
    normalized_response = normalize_text(
        response_text[:MAX_CLASSIFICATION_BODY_CHARS]
    )
    return bool(
        normalized_title
        and len(normalized_title) >= 6
        and normalized_title in normalized_response
    )


def ensure_expected_target_identity(
    target: JobHealthTarget,
    *,
    expected_source_name: str,
    expected_source_url: str,
) -> None:
    """Validate immutable target identity without granting source authority."""

    if target.source_name != expected_source_name:
        raise ValueError(
            "Source identity mismatch: "
            f"expected={expected_source_name!r} actual={target.source_name!r}"
        )
    if target.source_url != expected_source_url:
        raise ValueError(
            "Source URL mismatch: "
            f"expected={expected_source_url!r} actual={target.source_url!r}"
        )
    if not target.title.strip():
        raise ValueError("Target Silver title is empty")

    parsed = urlsplit(target.source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Target source_url is not an absolute HTTP(S) URL")


def ensure_expected_target(
    target: JobHealthTarget,
    *,
    expected_source_name: str,
    expected_source_url: str,
) -> None:
    """Validate exact-detail target identity plus historical source authority."""

    ensure_expected_target_identity(
        target,
        expected_source_name=expected_source_name,
        expected_source_url=expected_source_url,
    )

    if (
        target.canonical_source_type not in EMPLOYER_ORIGIN_HEALTH_SOURCE_TYPES
        and target.raw_source_type not in EMPLOYER_ORIGIN_HEALTH_SOURCE_TYPES
    ):
        raise ValueError(
            "Target is not an employer_origin_career_site or "
            "employer_origin_ats_backed_career_site vacancy"
        )


def fetch_exact_detail(
    url: str,
    *,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
) -> HttpProbeResult:
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
            },
            timeout=timeout_seconds,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        return HttpProbeResult(
            status_code=None,
            final_url=url,
            response_text="",
            redirect_count=0,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    return HttpProbeResult(
        status_code=response.status_code,
        final_url=response.url or url,
        response_text=response.text,
        redirect_count=len(response.history),
    )


def classify_exact_detail(
    target: JobHealthTarget,
    probe: HttpProbeResult,
) -> HealthClassification:
    url_identity_match = (
        normalize_url_identity(target.source_url)
        == normalize_url_identity(probe.final_url)
    )
    response_scope = probe.response_text[:MAX_CLASSIFICATION_BODY_CHARS]
    title_match = title_is_confirmed(target.title, response_scope)
    closure_marker = explicit_vacancy_closure_marker(response_scope)
    response_bytes = len(probe.response_text.encode("utf-8"))

    evidence: dict[str, object] = {
        "requested_url": target.source_url,
        "final_url": probe.final_url,
        "http_status": probe.status_code,
        "redirect_count": probe.redirect_count,
        "url_identity_match": url_identity_match,
        "title_match": title_match,
        "explicit_closure_marker": closure_marker,
        "response_bytes": response_bytes,
        "error_type": probe.error_type,
    }

    if probe.error_type is not None:
        return HealthClassification(
            outcome=OUTCOME_UNVERIFIABLE,
            coverage=COVERAGE_EXACT_DETAIL,
            evidence_reason="network_or_transport_failure",
            evidence=evidence,
        )

    if probe.status_code == 410:
        return HealthClassification(
            outcome=OUTCOME_CLOSED,
            coverage=COVERAGE_EXACT_DETAIL,
            evidence_reason="http_410_gone_on_exact_detail",
            evidence=evidence,
        )

    if probe.status_code == 404:
        return HealthClassification(
            outcome=OUTCOME_UNVERIFIABLE,
            coverage=COVERAGE_EXACT_DETAIL,
            evidence_reason="http_404_requires_source_specific_closure_validation",
            evidence=evidence,
        )

    if probe.status_code is not None and 200 <= probe.status_code < 400:
        if not url_identity_match:
            return HealthClassification(
                outcome=OUTCOME_UNVERIFIABLE,
                coverage=COVERAGE_EXACT_DETAIL,
                evidence_reason="final_url_changed_concrete_identity",
                evidence=evidence,
            )
        if closure_marker is not None:
            return HealthClassification(
                outcome=OUTCOME_CLOSED,
                coverage=COVERAGE_EXACT_DETAIL,
                evidence_reason="explicit_vacancy_unavailable_on_exact_detail",
                evidence=evidence,
            )
        if not title_match:
            return HealthClassification(
                outcome=OUTCOME_UNVERIFIABLE,
                coverage=COVERAGE_EXACT_DETAIL,
                evidence_reason="vacancy_title_not_confirmed_on_detail_page",
                evidence=evidence,
            )
        return HealthClassification(
            outcome=OUTCOME_SEEN_ACTIVE,
            coverage=COVERAGE_EXACT_DETAIL,
            evidence_reason="exact_detail_url_and_title_confirmed",
            evidence=evidence,
        )

    return HealthClassification(
        outcome=OUTCOME_UNVERIFIABLE,
        coverage=COVERAGE_EXACT_DETAIL,
        evidence_reason="http_status_not_authoritative_for_lifecycle",
        evidence=evidence,
    )


def build_health_probe_manifest(
    *,
    silver_job_id: int,
    expected_source_name: str,
    expected_source_url: str,
    apply: bool,
    approval_token: str | None,
    observed_by: str | None,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
    repository: JobLifecycleHealthRepository | None = None,
    fetcher=fetch_exact_detail,
) -> dict[str, object]:
    if silver_job_id <= 0:
        raise ValueError("silver_job_id must be a positive integer")
    if not expected_source_name.strip():
        raise ValueError("expected_source_name must not be empty")
    if not expected_source_url.strip():
        raise ValueError("expected_source_url must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    if apply:
        if approval_token != APPROVAL_TOKEN:
            raise ValueError("Invalid lifecycle health approval token")
        if observed_by is None or not observed_by.strip():
            raise ValueError("--observed-by is required for --apply")

    repository = repository or JobLifecycleHealthRepository()
    target = repository.load_target(silver_job_id)
    ensure_expected_target(
        target,
        expected_source_name=expected_source_name,
        expected_source_url=expected_source_url,
    )

    probe = fetcher(
        target.source_url,
        timeout_seconds=timeout_seconds,
    )
    classification = classify_exact_detail(target, probe)

    observation_id: int | None = None
    if apply:
        observation_id = repository.append_health_observation(
            expected_target=target,
            classification=classification,
            observed_by=observed_by or "",
        )

    return {
        "status": "job_lifecycle_health_probe",
        "mode": "apply" if apply else "dry_run",
        "target": asdict(target),
        "classification": {
            "outcome": classification.outcome,
            "coverage": classification.coverage,
            "evidence_reason": classification.evidence_reason,
            "evidence": classification.evidence,
        },
        "write": {
            "requested": apply,
            "applied": observation_id is not None,
            "job_health_observation_id": observation_id,
            "approval_token_required": APPROVAL_TOKEN if apply else None,
            "observed_by": observed_by if apply else None,
        },
        "boundary": {
            "http_requests": 1,
            "full_html_persisted": False,
            "bronze_write": False,
            "silver_write": False,
            "ranking_write": False,
            "application_write": False,
            "source_or_scheduler_write": False,
            "provider_or_llm": False,
            "health_observation_write": bool(apply),
        },
    }
