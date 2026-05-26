# Preview public Personio XML source targets.
#
# Defensive spike:
# - one XML request per explicit source target
# - no database writes
# - no detail-page fetching
# - search profile and search terms are read from the local DB
#
# Usage:
#   python -m scripts.preview_personio_xml_targets --list-profiles
#   python -m scripts.preview_personio_xml_targets --profile-id 9 --use-candidate-targets

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable

import psycopg
import requests

from src.config import get_database_config


CANDIDATE_TARGET_HOSTS = [
    "schluetersche-mediengruppe.jobs.personio.de",
    "it-p.jobs.personio.de",
    "eraneos.jobs.personio.de",
    "1komma5grad.jobs.personio.de",
    "xibix-solutions-gmbh.jobs.personio.de",
    "otl-akademie.jobs.personio.de",
    "loyos-bi.jobs.personio.de",
]

ACQUISITION_MODE = "public_xml_feed_with_local_keyword_filter"


@dataclass(frozen=True)
class SearchProfile:
    id: int
    profile_name: str
    source_name: str
    search_location: str
    search_radius_km: int | None
    is_active: bool


@dataclass(frozen=True)
class SearchTerm:
    id: int
    search_term: str
    is_active: bool


@dataclass(frozen=True)
class PersonioJobPreview:
    source_target: str
    external_job_id: str
    title: str
    location: str
    department: str
    employment_type: str
    schedule: str
    url: str
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class TargetPreview:
    source_target: str
    status: str
    total_jobs: int
    matching_jobs: list[PersonioJobPreview]
    error: str = ""


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def local_name(element: ET.Element) -> str:
    return element.tag.split("}")[-1]


def first_text(element: ET.Element, names: Iterable[str]) -> str:
    wanted = {name.lower() for name in names}

    for child in element.iter():
        tag = local_name(child).lower()
        if tag in wanted:
            value = normalize_whitespace(child.text)
            if value:
                return value

    return ""


def all_text(element: ET.Element) -> str:
    parts = [normalize_whitespace(value) for value in element.itertext()]
    return " ".join(part for part in parts if part)


def list_profiles() -> tuple[list[SearchProfile], dict[int, list[SearchTerm]]]:
    config = get_database_config()

    with psycopg.connect(**config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    profile_name,
                    source_name,
                    search_location,
                    search_radius_km,
                    is_active
                FROM search_profiles
                ORDER BY id;
                """
            )
            profiles = [
                SearchProfile(
                    id=row[0],
                    profile_name=row[1],
                    source_name=row[2],
                    search_location=row[3],
                    search_radius_km=row[4],
                    is_active=row[5],
                )
                for row in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT
                    search_profile_id,
                    id,
                    search_term,
                    is_active
                FROM search_terms
                ORDER BY search_profile_id, id;
                """
            )

            terms_by_profile: dict[int, list[SearchTerm]] = {}
            for row in cursor.fetchall():
                profile_id = row[0]
                terms_by_profile.setdefault(profile_id, []).append(
                    SearchTerm(
                        id=row[1],
                        search_term=row[2],
                        is_active=row[3],
                    )
                )

    return profiles, terms_by_profile


def print_profiles() -> None:
    profiles, terms_by_profile = list_profiles()

    print()
    print("=== Search Profiles and Terms ===")
    print()

    for profile in profiles:
        active_marker = "active" if profile.is_active else "inactive"
        print(
            f"[{profile.id}] {profile.profile_name} "
            f"source={profile.source_name} "
            f"location={profile.search_location} "
            f"radius_km={profile.search_radius_km} "
            f"status={active_marker}"
        )

        terms = terms_by_profile.get(profile.id, [])
        if not terms:
            print("    - no search terms")
            continue

        for term in terms:
            term_marker = "active" if term.is_active else "inactive"
            print(f"    - [{term.id}] {term.search_term} ({term_marker})")


def load_profile(profile_id: int | None, profile_name: str | None) -> tuple[SearchProfile, list[SearchTerm]]:
    profiles, terms_by_profile = list_profiles()

    if profile_id is not None and profile_name is not None:
        raise SystemExit("Use either --profile-id or --profile-name, not both.")

    if profile_id is not None:
        matches = [profile for profile in profiles if profile.id == profile_id]
    elif profile_name is not None:
        matches = [profile for profile in profiles if profile.profile_name == profile_name]
    else:
        raise SystemExit("No profile selected. Run with --list-profiles first, then use --profile-id.")

    if not matches:
        raise SystemExit("Selected search profile does not exist in the local DB.")

    if len(matches) > 1:
        raise SystemExit("Selected search profile is ambiguous. Use --profile-id.")

    profile = matches[0]
    terms = [term for term in terms_by_profile.get(profile.id, []) if term.is_active]

    if not terms:
        raise SystemExit("Selected search profile has no active search terms.")

    return profile, terms


def normalize_source_target(value: str) -> str:
    value = value.strip()

    if not value:
        raise ValueError("Empty source target is not allowed.")

    if value.startswith("https://"):
        value = value.removeprefix("https://")

    value = value.rstrip("/")

    if "/" in value:
        value = value.split("/", 1)[0]

    if "." not in value:
        value = f"{value}.jobs.personio.de"

    return value


def personio_xml_url(source_target: str, language: str) -> str:
    return f"https://{source_target}/xml?language={language}"


def extract_jobs(xml_content: bytes, source_target: str, terms: list[SearchTerm]) -> list[PersonioJobPreview]:
    root = ET.fromstring(xml_content)
    positions = [element for element in root.iter() if local_name(element).lower() == "position"]

    jobs: list[PersonioJobPreview] = []

    for position in positions:
        external_job_id = first_text(position, {"id"})
        title = first_text(position, {"name", "title", "jobtitle"})
        location = first_text(position, {"office", "location", "city"})
        department = first_text(position, {"department", "subcompany"})
        employment_type = first_text(position, {"employmenttype", "employment_type"})
        schedule = first_text(position, {"schedule"})
        text_for_matching = all_text(position).lower()

        matched_terms = tuple(
            term.search_term
            for term in terms
            if term.search_term.lower() in text_for_matching
        )

        if not title:
            continue

        url = ""
        if external_job_id:
            url = f"https://{source_target}/job/{external_job_id}?language=de"

        jobs.append(
            PersonioJobPreview(
                source_target=f"personio:{source_target}",
                external_job_id=external_job_id,
                title=title,
                location=location,
                department=department,
                employment_type=employment_type,
                schedule=schedule,
                url=url,
                matched_terms=matched_terms,
            )
        )

    return jobs


def fetch_target(source_target: str, language: str, timeout_seconds: int, terms: list[SearchTerm]) -> TargetPreview:
    url = personio_xml_url(source_target, language)

    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={
                "User-Agent": "job-application-pipeline-personio-preview/0.1",
                "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
            },
        )
    except requests.RequestException as exc:
        return TargetPreview(
            source_target=f"personio:{source_target}",
            status="request_error",
            total_jobs=0,
            matching_jobs=[],
            error=str(exc),
        )

    if response.status_code != 200:
        return TargetPreview(
            source_target=f"personio:{source_target}",
            status=f"http_{response.status_code}",
            total_jobs=0,
            matching_jobs=[],
            error=response.text[:160].replace("\n", " "),
        )

    try:
        jobs = extract_jobs(response.content, source_target, terms)
    except ET.ParseError as exc:
        return TargetPreview(
            source_target=f"personio:{source_target}",
            status="xml_parse_error",
            total_jobs=0,
            matching_jobs=[],
            error=str(exc),
        )

    matching_jobs = [job for job in jobs if job.matched_terms]

    return TargetPreview(
        source_target=f"personio:{source_target}",
        status="ok",
        total_jobs=len(jobs),
        matching_jobs=matching_jobs,
    )


def print_preview(
    profile: SearchProfile,
    terms: list[SearchTerm],
    results: list[TargetPreview],
    max_matches_per_target: int,
) -> None:
    print()
    print("=== Personio Source Target Preview ===")
    print()
    print(f"search_profile_id:   {profile.id}")
    print(f"search_profile_name: {profile.profile_name}")
    print(f"profile_source_name: {profile.source_name}")
    print("source_family:       personio")
    print("lineage_mode:        preview_only_no_db_write")
    print(f"search_location:     {profile.search_location}")
    print(f"search_radius_km:    {profile.search_radius_km}")
    print(f"acquisition_mode:    {ACQUISITION_MODE}")
    print("matching_mode:       simple_case_insensitive_term_match")
    print()
    print("active_search_terms:")
    for term in terms:
        print(f"- [{term.id}] {term.search_term}")

    print()
    print(
        "source_target".ljust(52)
        + " | "
        + "status".ljust(16)
        + " | "
        + "jobs".rjust(4)
        + " | "
        + "matches".rjust(7)
    )
    print("-" * 88)

    for result in results:
        print(
            result.source_target.ljust(52)
            + " | "
            + result.status.ljust(16)
            + " | "
            + str(result.total_jobs).rjust(4)
            + " | "
            + str(len(result.matching_jobs)).rjust(7)
        )

    print()
    print("=== Matching Jobs ===")

    any_matches = False

    for result in results:
        if not result.matching_jobs:
            continue

        any_matches = True
        print()
        print(f"[{result.source_target}]")

        for job in result.matching_jobs[:max_matches_per_target]:
            location = f" — {job.location}" if job.location else ""
            department = f" ({job.department})" if job.department else ""
            matches = ", ".join(job.matched_terms)
            print(f"- {job.title}{location}{department}")
            print(f"  matched_terms: {matches}")
            if job.url:
                print(f"  source_url_candidate: {job.url}")

    if not any_matches:
        print()
        print("No matching jobs found for the selected search terms.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-profiles", action="store_true")
    parser.add_argument("--profile-id", type=int)
    parser.add_argument("--profile-name")
    parser.add_argument("--target", action="append", dest="targets")
    parser.add_argument("--use-candidate-targets", action="store_true")
    parser.add_argument("--language", default="de")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--max-matches-per-target", type=int, default=5)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.list_profiles:
        print_profiles()
        return

    profile, terms = load_profile(
        profile_id=args.profile_id,
        profile_name=args.profile_name,
    )

    target_values: list[str] = []

    if args.targets:
        target_values.extend(args.targets)

    if args.use_candidate_targets:
        target_values.extend(CANDIDATE_TARGET_HOSTS)

    if not target_values:
        raise SystemExit(
            "No Personio source targets selected. Use --target or --use-candidate-targets."
        )

    source_targets = []
    for value in target_values:
        source_target = normalize_source_target(value)
        if source_target not in source_targets:
            source_targets.append(source_target)

    results = [
        fetch_target(
            source_target=source_target,
            language=args.language,
            timeout_seconds=args.timeout,
            terms=terms,
        )
        for source_target in source_targets
    ]

    print_preview(
        profile=profile,
        terms=terms,
        results=results,
        max_matches_per_target=args.max_matches_per_target,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
