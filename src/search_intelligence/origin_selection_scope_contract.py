"""Downgrade selected origins with unresolved entity or locale scope.

A URL may be a real career source and still belong to the wrong legal entity,
country tenant, or a different company with the same short brand. This contract
runs after deterministic/provider selection and converts only those ambiguous
selections to operator review.

Generic signals:

- conflicting country-code TLDs or leading country path segments;
- shared ATS tenant slugs ending in a conflicting uppercase country code;
- multi-token employers represented only by a short brand on an unusual TLD.

No company or URL is allowlisted. The original candidate is retained as a
recommended review URL and all database/write boundaries remain unchanged.
"""

from __future__ import annotations

from dataclasses import replace
import re
from typing import Mapping
from urllib.parse import urlparse

import src.search_intelligence.origin_source_discovery_agent as origin_agent
from src.search_intelligence.origin_url_default_repair import (
    RepairStage,
    compatibility_payload,
    finalize_outcome,
)

COUNTRY_CODES = {
    "at",
    "au",
    "be",
    "br",
    "ca",
    "ch",
    "cn",
    "cz",
    "de",
    "dk",
    "es",
    "fi",
    "fr",
    "gb",
    "gr",
    "hu",
    "ie",
    "in",
    "it",
    "jp",
    "lu",
    "mx",
    "nl",
    "no",
    "pl",
    "pt",
    "ro",
    "se",
    "sk",
    "tr",
    "uk",
    "us",
}
GLOBAL_OR_NEUTRAL_TLDS = {
    "com",
    "org",
    "net",
    "eu",
    "group",
    "jobs",
    "career",
    "careers",
}


def _target_country(target_locale: str | None) -> str | None:
    parts = [part.lower() for part in re.split(r"[-_]", str(target_locale or "")) if part]
    if len(parts) >= 2 and len(parts[-1]) == 2 and parts[-1].isalpha():
        return parts[-1]
    return None


def _stage_from_mapping(raw: Mapping[str, object]) -> RepairStage:
    return RepairStage(
        name=str(raw.get("name") or ""),
        attempted=bool(raw.get("attempted")),
        status=str(raw.get("status") or ""),
        decision=str(raw.get("decision")) if raw.get("decision") is not None else None,
        selected_url=(
            str(raw.get("selected_url"))
            if raw.get("selected_url") is not None
            else None
        ),
        recommended_url=(
            str(raw.get("recommended_url"))
            if raw.get("recommended_url") is not None
            else None
        ),
        confidence_score=float(raw.get("confidence_score") or 0.0),
        candidate_count=int(raw.get("candidate_count") or 0),
        provider_request_count=int(raw.get("provider_request_count") or 0),
        reason=str(raw.get("reason") or ""),
        blocker=str(raw.get("blocker")) if raw.get("blocker") is not None else None,
    )


def _scope_reason(
    *,
    selected_url: str,
    company_name: str,
    target_locale: str | None,
) -> str | None:
    parsed = urlparse(selected_url)
    hostname = str(parsed.hostname or "").lower().strip(".")
    if not hostname:
        return "selected origin has no hostname"

    target_country = _target_country(target_locale)
    host_parts = hostname.split(".")
    tld = host_parts[-1] if host_parts else ""
    if target_country and tld in COUNTRY_CODES and tld != target_country:
        return f"selected origin country TLD {tld} conflicts with target country {target_country}"

    path_segments = [segment for segment in parsed.path.split("/") if segment]
    if target_country and path_segments:
        leading = path_segments[0].lower()
        if leading in COUNTRY_CODES and leading != target_country:
            return (
                f"selected origin leading country path {leading} conflicts with "
                f"target country {target_country}"
            )

    if target_country and origin_agent.is_known_ats_provider_domain(hostname) and path_segments:
        tenant = path_segments[0]
        match = re.search(r"([A-Z]{2})$", tenant)
        if match:
            tenant_country = match.group(1).lower()
            if tenant_country in COUNTRY_CODES and tenant_country != target_country:
                return (
                    f"ATS tenant country suffix {tenant_country} conflicts with "
                    f"target country {target_country}"
                )

    company_tokens = [
        token
        for token in origin_agent.tokenize(company_name)
        if token not in origin_agent.LEGAL_OR_GENERIC_TOKENS
        and token not in {"and", "und", "the", "der", "die", "das"}
    ]
    host_text = re.sub(r"[^a-z0-9]+", "", hostname)
    matched = [token for token in company_tokens if token in host_text]
    if (
        len(company_tokens) >= 2
        and matched
        and all(len(token) <= 4 for token in matched)
        and tld not in GLOBAL_OR_NEUTRAL_TLDS
        and tld not in COUNTRY_CODES
    ):
        return (
            "multi-token employer is represented only by a short brand on an "
            f"unusual .{tld} origin; exact entity remains unproven"
        )

    return None


def normalize_selection_scope_outcome(
    payload: Mapping[str, object],
    *,
    target_locale: str | None,
) -> dict[str, object]:
    """Return a payload with ambiguous selected scope converted to review."""

    result = dict(payload)
    repair = payload.get("default_repair")
    if not isinstance(repair, Mapping):
        return result
    selected_url = str(repair.get("selected_url") or payload.get("selected_url") or "").strip()
    if not selected_url:
        return result

    reason = _scope_reason(
        selected_url=selected_url,
        company_name=str(repair.get("company_name") or payload.get("company_name") or ""),
        target_locale=target_locale,
    )
    if reason is None:
        return result

    raw_stages = repair.get("stages")
    if not isinstance(raw_stages, list):
        return result

    transformed: list[RepairStage] = []
    changed = False
    for raw in raw_stages:
        if not isinstance(raw, Mapping):
            continue
        stage = _stage_from_mapping(raw)
        if stage.selected_url != selected_url:
            transformed.append(stage)
            continue
        changed = True
        transformed.append(
            replace(
                stage,
                status="manual_review",
                decision="manual_review_required",
                selected_url=None,
                recommended_url=selected_url,
                reason=f"{stage.reason}; {reason}".strip("; "),
            )
        )

    if not changed:
        return result

    outcome = finalize_outcome(
        company_key=str(repair.get("company_key") or payload.get("company_key") or ""),
        company_name=str(repair.get("company_name") or payload.get("company_name") or ""),
        stages=transformed,
    )
    normalized = compatibility_payload(outcome, last_discovery_payload=result)
    normalized["selection_scope_review_required"] = True
    normalized["selection_scope_reason"] = reason
    normalized["selection_scope_candidate_url"] = selected_url
    return normalized


__all__ = [
    "normalize_selection_scope_outcome",
]
